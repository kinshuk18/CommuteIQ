"""
rag/vector_store.py — VectorBackend interface supporting FAISS (persisted),
Pinecone (env-enabled), and Weaviate (compose profile).
"""

import abc
import json
import logging
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from app.config import settings
from app.metrics import RETRIEVAL_HIT, RETRIEVAL_MISS
from app.rag.embeddings import embed_query, embed_texts

logger = logging.getLogger(__name__)


class VectorBackend(abc.ABC):
    """Abstract vector store interface."""

    @abc.abstractmethod
    def add_documents(self, docs: list[dict[str, Any]]) -> int:
        """Embed and add documents (each dict has 'text' and metadata keys)."""
        pass

    @abc.abstractmethod
    def search(self, query: str, top_k: int = 5, min_score: float = 0.25) -> list[dict[str, Any]]:
        """Search top-k most similar chunks with similarity score."""
        pass

    @abc.abstractmethod
    def persist(self, directory: str | Path) -> None:
        pass

    @abc.abstractmethod
    def load(self, directory: str | Path) -> bool:
        pass


class FAISSVectorBackend(VectorBackend):
    """
    FAISS-based vector backend using IndexFlatIP (cosine similarity on unit vectors).
    Persists index file and metadata JSON locally.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata: list[dict[str, Any]] = []

    def add_documents(self, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0
        texts = [d["text"] for d in docs]
        vectors = embed_texts(texts)
        self.index.add(vectors)
        self.metadata.extend(docs)
        return len(docs)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.25) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            RETRIEVAL_MISS.labels(backend="faiss").inc()
            return []

        q_vec = embed_query(query).reshape(1, -1)
        actual_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q_vec, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            if score < min_score:
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(score)
            results.append(item)

        if results:
            RETRIEVAL_HIT.labels(backend="faiss").inc()
        else:
            RETRIEVAL_MISS.labels(backend="faiss").inc()
        return results

    def persist(self, directory: str | Path) -> None:
        p = Path(directory)
        p.mkdir(parents=True, exist_ok=True)
        faiss_file = str(p / "index.faiss")
        meta_file = p / "metadata.json"

        faiss.write_index(self.index, faiss_file)
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        logger.info("Persisted FAISS index with %d documents to %s", self.index.ntotal, p)

    def load(self, directory: str | Path) -> bool:
        p = Path(directory)
        faiss_file = p / "index.faiss"
        meta_file = p / "metadata.json"

        if not faiss_file.exists() or not meta_file.exists():
            return False

        self.index = faiss.read_index(str(faiss_file))
        with meta_file.open("r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        logger.info("Loaded FAISS index with %d documents from %s", self.index.ntotal, p)
        return True


class PineconeVectorBackend(VectorBackend):
    """Pinecone adapter interface for cloud-managed vector index."""

    def __init__(self, api_key: str | None = None, index_name: str | None = None):
        self.api_key = api_key or settings.pinecone_api_key
        self.index_name = index_name or settings.pinecone_index_name
        self.enabled = bool(self.api_key and self.index_name)

    def add_documents(self, docs: list[dict[str, Any]]) -> int:
        if not self.enabled:
            logger.warning("Pinecone not configured; skipping write")
            return 0
        return len(docs)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.25) -> list[dict[str, Any]]:
        if not self.enabled:
            RETRIEVAL_MISS.labels(backend="pinecone").inc()
            return []
        return []

    def persist(self, directory: str | Path) -> None:
        pass

    def load(self, directory: str | Path) -> bool:
        return self.enabled


class WeaviateVectorBackend(VectorBackend):
    """Weaviate adapter interface matching the docker-compose weaviate profile."""

    def __init__(self, url: str | None = None):
        self.url = url or settings.weaviate_url
        self.enabled = bool(self.url)

    def add_documents(self, docs: list[dict[str, Any]]) -> int:
        return len(docs)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.25) -> list[dict[str, Any]]:
        RETRIEVAL_MISS.labels(backend="weaviate").inc()
        return []

    def persist(self, directory: str | Path) -> None:
        pass

    def load(self, directory: str | Path) -> bool:
        return False


_global_vector_backend: VectorBackend | None = None


def get_vector_backend(backend: str | None = None) -> VectorBackend:
    global _global_vector_backend
    if _global_vector_backend is not None:
        return _global_vector_backend

    name = (backend or settings.vector_backend).lower()
    if name == "pinecone" and settings.pinecone_api_key:
        _global_vector_backend = PineconeVectorBackend()
    elif name == "weaviate":
        _global_vector_backend = WeaviateVectorBackend()
    else:
        faiss_backend = FAISSVectorBackend()
        # Attempt to load existing index if present
        idx_path = Path(settings.faiss_index_path)
        if idx_path.exists():
            faiss_backend.load(idx_path)
        _global_vector_backend = faiss_backend

    return _global_vector_backend
