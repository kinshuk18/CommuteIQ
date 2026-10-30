# Multi-stage build for the Python AI service.
# Stage 1: install deps via uv (10x faster); Stage 2: slim runtime (non-root).

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM python:3.11-slim AS deps
WORKDIR /build

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --prefix=/install .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

# Create non-root user
RUN groupadd -r commuteiq && useradd -r -g commuteiq -s /sbin/nologin commuteiq

COPY --from=deps /install /usr/local
COPY app app
COPY faiss_index faiss_index
COPY mlruns mlruns

RUN mkdir -p faiss_index mlruns && chown -R commuteiq:commuteiq /app

USER commuteiq

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=12 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1", \
     "--log-level", "info"]
