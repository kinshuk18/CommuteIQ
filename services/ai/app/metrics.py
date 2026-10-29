"""
metrics.py — Prometheus metrics for the AI service.

Instruments:
  - HTTP request latency (labelled by endpoint)
  - LLM call latency + token usage
  - Vector retrieval hit rate
  - Redis cache hit/miss ratio
"""

from prometheus_client import Counter, Histogram, Gauge

# HTTP request duration
REQUEST_LATENCY = Histogram(
    "ai_request_duration_seconds",
    "End-to-end HTTP request latency",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# LLM call latency
LLM_LATENCY = Histogram(
    "ai_llm_duration_seconds",
    "LLM API call latency",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# LLM token usage (prompt + completion separately)
LLM_TOKENS = Counter(
    "ai_llm_tokens_total",
    "Cumulative LLM token usage",
    ["provider", "model", "token_type"],  # token_type: prompt | completion
)

# Retrieval hit rate: a "hit" = at least one chunk returned with score > threshold
RETRIEVAL_HIT = Counter(
    "ai_retrieval_hit_total",
    "Vector retrieval hits (≥1 chunk above score threshold)",
    ["backend"],
)
RETRIEVAL_MISS = Counter(
    "ai_retrieval_miss_total",
    "Vector retrieval misses (zero chunks above score threshold)",
    ["backend"],
)

# Redis cache
CACHE_HIT = Counter(
    "ai_cache_hit_total",
    "Redis cache hits",
    ["cache_name"],
)
CACHE_MISS = Counter(
    "ai_cache_miss_total",
    "Redis cache misses",
    ["cache_name"],
)

# ML model inference latency
ML_INFERENCE_LATENCY = Histogram(
    "ai_ml_inference_duration_seconds",
    "ML model predict() latency",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

# Active requests (gauge)
ACTIVE_REQUESTS = Gauge(
    "ai_active_requests",
    "Number of in-flight requests",
)
