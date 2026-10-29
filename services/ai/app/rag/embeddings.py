"""
rag/embeddings.py — Local HuggingFace sentence-transformers embedding wrapper.
Uses BAAI/bge-small-en-v1.5 (dimension 384) with in-memory caching.
"""

import logging
from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Encode a batch of strings into normalized float32 vectors."""
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype(np.float32)


def embed_query(query: str) -> np.ndarray:
    """Encode a single query string into a 1D normalized float32 vector."""
    return embed_texts([query])[0]
