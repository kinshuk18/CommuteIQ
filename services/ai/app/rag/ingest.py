"""
rag/ingest.py — Ingestion pipeline over data/raw/docs into the vector backend.
Extracts real document text and JSON metadata, splits into semantically coherent
chunks, and builds the persisted vector index.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.rag.vector_store import get_vector_backend

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "raw" / "docs"


def chunk_text(text: str, max_chunk_chars: int = 600, overlap_chars: int = 100) -> list[str]:
    """Split text on paragraph/sentence boundaries within character budget."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_chunk_chars:
            current = f"{current}\n\n{p}".strip()
        else:
            if current:
                chunks.append(current)
            if len(p) > max_chunk_chars:
                # Split large paragraphs on sentences
                sentences = re.split(r"(?<=[.!?])\s+", p)
                sub_chunk = ""
                for s in sentences:
                    if len(sub_chunk) + len(s) + 1 <= max_chunk_chars:
                        sub_chunk = f"{sub_chunk} {s}".strip()
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = s
                current = sub_chunk
            else:
                current = p

    if current:
        chunks.append(current)
    return chunks


def ingest_corpus(docs_dir: Path | None = None) -> dict[str, Any]:
    """Ingest all policy and fare documents from data/raw/docs."""
    source_dir = docs_dir or DOCS_DIR
    if not source_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {source_dir}")

    backend = get_vector_backend()
    all_chunks = []
    files_processed = 0

    txt_files = sorted(source_dir.glob("*.txt"))
    for txt_path in txt_files:
        meta_path = txt_path.with_suffix(".json")
        meta = {}
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as exc:
                logger.warning("Failed to parse metadata %s: %s", meta_path.name, exc)

        with txt_path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()

        if not content:
            continue

        raw_chunks = chunk_text(content)
        for i, chunk in enumerate(raw_chunks):
            doc_item = {
                "id": f"{meta.get('id', txt_path.stem)}_p{i+1}",
                "text": chunk,
                "title": meta.get("title", txt_path.stem.replace("-", " ").title()),
                "url": meta.get("url", ""),
                "trust_tier": meta.get("trust_tier", "UNVERIFIED").upper(),
                "authority": meta.get("authority") or meta.get("source", "Bangalore Transit Docs"),
                "doc_date": meta.get("doc_date", "2024-2025"),
                "page": i + 1,
            }
            all_chunks.append(doc_item)
        files_processed += 1

    added_count = backend.add_documents(all_chunks)
    backend.persist(settings.faiss_index_path)

    summary = {
        "files_processed": files_processed,
        "chunks_indexed": added_count,
        "index_path": str(settings.faiss_index_path),
        "backend": settings.vector_backend,
    }
    logger.info("Ingestion completed: %s", summary)
    return summary
