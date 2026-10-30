"""
llm/client.py — LLM strategy and factory with multi-provider fallback and on-disk caching.

Supported providers:
  - openai_compat (default): Gemini / Groq / OpenAI endpoints.
  - groq fallback: Triggered automatically on 429/5xx if GROQ_API_KEY is present.
  - anthropic: Claude API adapter with mock fallback for testing.

Features:
  - Persistent SQLite response cache (keyed by sha256 of model + prompt)
  - Cap of <= 2 calls per request
  - Prometheus metrics for latency and token counts
"""

import abc
import hashlib
import logging
import os
import random
import sqlite3
import time
from typing import Any

from openai import OpenAI
from app.config import settings
from app.metrics import LLM_LATENCY, LLM_TOKENS

logger = logging.getLogger(__name__)


class LLMCache:
    """Persistent SQLite cache for LLM completions."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.llm_cache_path
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS completion_cache (
                        prompt_hash TEXT PRIMARY KEY,
                        provider TEXT,
                        model TEXT,
                        response TEXT,
                        created_at REAL
                    )
                    """
                )
        except Exception as exc:
            logger.warning("Failed to initialize SQLite LLM cache at %s: %s", self.db_path, exc)

    @staticmethod
    def hash_key(model: str, system: str | None, prompt: str) -> str:
        h = hashlib.sha256()
        h.update(model.encode("utf-8"))
        h.update((system or "").encode("utf-8"))
        h.update(prompt.encode("utf-8"))
        return h.hexdigest()

    def get(self, key: str) -> str | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT response FROM completion_cache WHERE prompt_hash = ?", (key,))
                row = cur.fetchone()
                if row:
                    return str(row[0])
        except Exception as exc:
            logger.debug("Cache lookup failed: %s", exc)
        return None

    def set(self, key: str, response: str, provider: str, model: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO completion_cache
                    (prompt_hash, provider, model, response, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, provider, model, response, time.time()),
                )
        except Exception as exc:
            logger.debug("Cache store failed: %s", exc)


_CACHE = LLMCache()


class BaseLLMClient(abc.ABC):
    """Abstract interface for LLM calls."""

    @abc.abstractmethod
    def complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """Synchronously complete text from prompt."""
        pass


class OpenAICompatClient(BaseLLMClient):
    """
    OpenAI-compatible client adapter.
    Primary: Gemini or configured LLM_BASE_URL.
    Fallback: Groq (https://api.groq.com/openai/v1) on 429/5xx.
    Cap: <= 2 total remote calls per complete().
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 5,
        max_retries: int = 1,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "gemini-2.0-flash"
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = min(max_retries, 1)  # cap total calls <= 2

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "missing-key",
            timeout=float(self.timeout),
            max_retries=0,
        )

        self._groq_client = None
        if settings.groq_api_key:
            self._groq_client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
                timeout=float(self.timeout),
                max_retries=0,
            )

    def complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        cache_key = _CACHE.hash_key(self.model, system, prompt)
        cached = _CACHE.get(cache_key)
        if cached:
            logger.info("LLM cache hit for model %s", self.model)
            return cached

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Call 1: Primary provider (Gemini / custom)
        t0 = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.2),
                max_tokens=kwargs.get("max_tokens", 1024),
                timeout=float(self.timeout),
            )
            elapsed = time.perf_counter() - t0
            LLM_LATENCY.labels(provider="openai_compat", model=self.model).observe(elapsed)
            if resp.usage:
                LLM_TOKENS.labels(provider="openai_compat", model=self.model, token_type="prompt").inc(
                    resp.usage.prompt_tokens or 0
                )
                LLM_TOKENS.labels(provider="openai_compat", model=self.model, token_type="completion").inc(
                    resp.usage.completion_tokens or 0
                )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                _CACHE.set(cache_key, content, "openai_compat", self.model)
                return content
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.warning("Primary LLM call failed in %.2fs: %s", elapsed, exc)

            # Call 2: Fallback to Groq if key is present and primary hit 429/5xx/quota
            if self._groq_client:
                groq_model = settings.groq_model
                logger.info("Attempting Groq fallback (%s)...", groq_model)
                try:
                    t1 = time.perf_counter()
                    resp = self._groq_client.chat.completions.create(
                        model=groq_model,
                        messages=messages,
                        temperature=kwargs.get("temperature", 0.2),
                        max_tokens=kwargs.get("max_tokens", 1024),
                        timeout=float(self.timeout),
                    )
                    elapsed1 = time.perf_counter() - t1
                    LLM_LATENCY.labels(provider="groq", model=groq_model).observe(elapsed1)
                    content = (resp.choices[0].message.content or "").strip()
                    if content:
                        _CACHE.set(cache_key, content, "groq", groq_model)
                        return content
                except Exception as groq_exc:
                    logger.warning("Groq fallback also failed: %s", groq_exc)
                    raise RuntimeError(f"All LLM providers failed: {exc} | {groq_exc}") from exc

            raise RuntimeError(f"LLM call failed: {exc}") from exc


class AnthropicClient(BaseLLMClient):
    """
    Claude API adapter.
    Uses real Anthropic SDK if configured, with deterministic mock fallback when api key is absent.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model
        self.mock_mode = not bool(self.api_key)

    def complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        cache_key = _CACHE.hash_key(self.model, system, prompt)
        cached = _CACHE.get(cache_key)
        if cached:
            return cached

        t0 = time.perf_counter()
        if self.mock_mode:
            time.sleep(0.05)
            elapsed = time.perf_counter() - t0
            LLM_LATENCY.labels(provider="anthropic_mock", model=self.model).observe(elapsed)
            LLM_TOKENS.labels(provider="anthropic_mock", model=self.model, token_type="prompt").inc(
                len(prompt.split())
            )
            LLM_TOKENS.labels(provider="anthropic_mock", model=self.model, token_type="completion").inc(25)
            ans = (
                "Verified facts indicate Namma Metro and BMTC provide direct connectivity. "
                "Citations: [1] Official Metro Fares."
            )
            _CACHE.set(cache_key, ans, "anthropic_mock", self.model)
            return ans

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            msg = client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1024),
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.perf_counter() - t0
            LLM_LATENCY.labels(provider="anthropic", model=self.model).observe(elapsed)
            ans = msg.content[0].text.strip()
            _CACHE.set(cache_key, ans, "anthropic", self.model)
            return ans
        except Exception as exc:
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc


def get_llm_client() -> BaseLLMClient:
    """Factory creating the configured LLM client."""
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicClient()
    return OpenAICompatClient()
