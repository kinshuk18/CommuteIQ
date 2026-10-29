"""
main.py — FastAPI application entry point for the CommuteIQ AI service.

Startup sequence:
  1. Initialise GTFSRouter (loads graph from Postgres)
  2. Load MLflow registered model (RuntimePredictor)
  3. Begin serving /health, /metrics, /plan, /ml/predict-runtime
     (RAG endpoints /ask and /ingest are added in Phase 4)
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.metrics import REQUEST_LATENCY, ACTIVE_REQUESTS
from app.router import init_router, get_router
from app.ml_model import RuntimePredictor, train_and_register
from app.rag.vector_store import get_vector_backend
from app.routes import plan, ml, ask, ingest

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI service starting …")
    # Load GTFS graph (may take a few seconds on first start)
    init_router(settings.db_url)
    # Load ML model from MLflow registry (non-fatal if not yet registered)
    RuntimePredictor.load()
    # Initialize vector backend (loads persisted index if available)
    get_vector_backend()
    logger.info("AI service ready")
    yield
    logger.info("AI service shutting down")


app = FastAPI(
    title="CommuteIQ AI Service",
    description=(
        "GTFS-based multimodal routing, ML runtime prediction, and RAG commute assistant "
        "for Bengaluru hybrid-work commuters."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record per-endpoint latency and track active request count."""
    endpoint = request.url.path
    ACTIVE_REQUESTS.inc()
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed = time.perf_counter() - t0
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(elapsed)
        ACTIVE_REQUESTS.dec()
    return response


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    """Liveness + readiness probe endpoint."""
    return {"status": "ok", "service": "commuteiq-ai"}


# ── prometheus metrics ────────────────────────────────────────────────────────

@app.get("/metrics", tags=["ops"])
async def metrics():
    """Prometheus scrape endpoint."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ── routers ───────────────────────────────────────────────────────────────────

app.include_router(plan.router, prefix="/plan", tags=["routing"])
app.include_router(ml.router, prefix="/ml", tags=["ml"])
app.include_router(ask.router, prefix="/ask", tags=["agent"])
app.include_router(ingest.router, prefix="/ingest", tags=["rag"])
