"""
llm/client.py — LLM strategy and factory with multi-provider support.

Supported providers:
  - openai_compat (default): Works with Gemini OpenAI endpoint, Groq, and official OpenAI.
  - anthropic: Claude API adapter with mock fallback for testing.

Features:
  - Configurable timeouts
  - Exponential backoff retries with jitter
  - Prometheus metrics for latency and token counts
"""

import abc
import logging
import random
import time
from typing import Any

from openai import OpenAI
from app.config import settings
from app.metrics import LLM_LATENCY, LLM_TOKENS

logger = logging.getLogger(__name__)


class BaseLLMClient(abc.ABC):
    """Abstract interface for LLM calls."""

    @abc.abstractmethod
    def complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """Synchronously complete text from prompt."""
        pass


class OpenAICompatClient(BaseLLMClient):
    """
    OpenAI-compatible client adapter.
    Defaults to Google Gemini OpenAI-compatible endpoint, but configurable to Groq or OpenAI.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "gemini-3.8-flash"
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = max_retries or settings.llm_max_retries
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "missing-key",
            timeout=float(self.timeout),
            max_retries=0,
        )

    def complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_exc = None
        for attempt in range(self.max_retries + 1):
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
                    LLM_TOKENS.labels(
                        provider="openai_compat", model=self.model, token_type="prompt"
                    ).inc(resp.usage.prompt_tokens or 0)
                    LLM_TOKENS.labels(
                        provider="openai_compat", model=self.model, token_type="completion"
                    ).inc(resp.usage.completion_tokens or 0)

                content = resp.choices[0].message.content or ""
                return content.strip()
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                logger.warning(
                    "LLM call attempt %d failed in %.2fs: %s", attempt + 1, elapsed, exc
                )
                last_exc = exc
                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    sleep_sec = (2 ** attempt) + random.uniform(0.1, 0.5)
                    time.sleep(sleep_sec)

        raise RuntimeError(f"LLM call failed after {self.max_retries + 1} attempts: {last_exc}")


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
        t0 = time.perf_counter()
        if self.mock_mode:
            # Deterministic mock response for offline CI / test environments
            time.sleep(0.05)
            elapsed = time.perf_counter() - t0
            LLM_LATENCY.labels(provider="anthropic_mock", model=self.model).observe(elapsed)
            LLM_TOKENS.labels(
                provider="anthropic_mock", model=self.model, token_type="prompt"
            ).inc(len(prompt.split()))
            LLM_TOKENS.labels(
                provider="anthropic_mock", model=self.model, token_type="completion"
            ).inc(25)
            return (
                "Verified facts indicate Namma Metro and BMTC provide direct connectivity. "
                "Citations: [1] Official Metro Fares."
            )

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
            if hasattr(msg, "usage") and msg.usage:
                LLM_TOKENS.labels(
                    provider="anthropic", model=self.model, token_type="prompt"
                ).inc(msg.usage.input_tokens)
                LLM_TOKENS.labels(
                    provider="anthropic", model=self.model, token_type="completion"
                ).inc(msg.usage.output_tokens)
            return msg.content[0].text.strip()
        except Exception as exc:
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc


def get_llm_client() -> BaseLLMClient:
    """Factory creating the configured LLM client."""
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicClient()
    return OpenAICompatClient()
