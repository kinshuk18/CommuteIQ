"""
routes/ingest.py — POST /ingest endpoint to trigger document corpus ingestion.
"""

from fastapi import APIRouter, HTTPException
from app.rag.ingest import ingest_corpus

router = APIRouter()


@router.post("", response_model=dict)
async def trigger_ingestion():
    """
    Ingest transit policies, fare rules, and guidelines from data/raw/docs into the vector store.
    """
    try:
        result = ingest_corpus()
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(500, f"Ingestion failed: {exc}") from exc
