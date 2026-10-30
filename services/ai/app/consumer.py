"""
consumer.py — aiokafka consumer for the ai-service.

Listens to `commute.plans` and `commute.feedback` topics and:
1. Updates Redis `popular_routes` ZSET (mirrors gateway's producer).
2. Computes and stores feature-drift stats (PSI) vs the training distribution.

Works gracefully when Kafka is disabled (KAFKA_ENABLED=false).
"""

import asyncio
import json
import logging
import os
import math
from collections import defaultdict
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

# Attempt aiokafka import; absent in dev without Kafka
try:
    from aiokafka import AIOKafkaConsumer
    _AIOKAFKA_AVAILABLE = True
except ImportError:
    _AIOKAFKA_AVAILABLE = False
    log.warning("aiokafka not installed — Kafka consumer disabled")

# Attempt Redis import
try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


def _kafka_enabled() -> bool:
    return os.environ.get("KAFKA_ENABLED", "true").lower() not in ("false", "0", "no")


# ---------------------------------------------------------------------------
# PSI (Population Stability Index) drift detection
# ---------------------------------------------------------------------------

# Training-time hour distribution bucketed into 4 quartiles:
# [0-6], [7-12], [13-18], [19-23]  (measured from real GTFS schedule)
_TRAIN_HOUR_DIST = np.array([0.10, 0.45, 0.30, 0.15], dtype=float)

_hour_counts: dict[int, int] = defaultdict(int)
_total_plans = 0


def _psi(expected: np.ndarray, actual: np.ndarray) -> float:
    """Population Stability Index between two normalised distributions."""
    # Clip to avoid log(0)
    e = np.clip(expected / expected.sum(), 1e-8, 1.0)
    a = np.clip(actual / actual.sum(), 1e-8, 1.0)
    return float(np.sum((a - e) * np.log(a / e)))


def _bucket(hour: int) -> int:
    if hour < 7:   return 0
    if hour < 13:  return 1
    if hour < 19:  return 2
    return 3


def _current_psi() -> float:
    if _total_plans < 20:
        return 0.0  # not enough data
    counts = np.array([_hour_counts.get(b, 0) for b in range(4)], dtype=float)
    return _psi(_TRAIN_HOUR_DIST, counts)


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

_redis_client: Any = None


async def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None and _REDIS_AVAILABLE:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        try:
            _redis_client = await aioredis.from_url(url, decode_responses=True)
        except Exception as exc:
            log.warning("Redis unavailable for consumer: %s", exc)
    return _redis_client


async def _record_plan(payload: dict) -> None:
    """Update popular_routes ZSET and drift stats from a plan event."""
    global _total_plans
    origin = payload.get("origin", "")
    dest   = payload.get("dest", "")
    hour   = int(payload.get("hour", 9))

    route_key = f"{origin}:{dest}"
    _hour_counts[_bucket(hour)] += 1
    _total_plans += 1

    psi = _current_psi()
    if psi > 0.2:
        log.warning("Feature drift detected: hour-distribution PSI=%.3f (>0.2 threshold)", psi)

    r = await _get_redis()
    if r:
        try:
            await r.zincrby("popular_routes", 1, route_key)
            await r.hset("drift_stats", mapping={
                "psi_hour": round(psi, 4),
                "total_plans": _total_plans,
            })
        except Exception as exc:
            log.warning("Redis write failed in consumer: %s", exc)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------

async def run_consumer() -> None:
    if not _kafka_enabled():
        log.info("KAFKA_ENABLED=false — consumer not started")
        return

    if not _AIOKAFKA_AVAILABLE:
        log.info("aiokafka unavailable — consumer not started")
        return

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092"))
    log.info("Starting Kafka consumer on %s", bootstrap)

    consumer = AIOKafkaConsumer(
        "commute.plans",
        "commute.feedback",
        bootstrap_servers=bootstrap,
        group_id="ai-service-consumer",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )

    try:
        await consumer.start()
        async for msg in consumer:
            try:
                payload = json.loads(msg.value.decode())
                if msg.topic == "commute.plans":
                    await _record_plan(payload)
            except Exception as exc:
                log.warning("Consumer message error: %s", exc)
    except asyncio.CancelledError:
        log.info("Kafka consumer cancelled")
    except Exception as exc:
        log.error("Kafka consumer fatal error: %s", exc)
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass
