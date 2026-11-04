"""
CURATOR — Embedding Service & FAISS Vector Store
Builds and queries a FAISS index over curriculum chunks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.logging import logger
from app.models.schemas import RetrievedChunk

settings = get_settings()

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("faiss.not_available", msg="Install faiss-cpu to enable vector search")


class EmbeddingService:
    """Manages text→vector encoding.

    Uses sentence-transformers when installed and the model can be loaded;
    otherwise falls back to a deterministic local TF-IDF + LSA encoder
    (fitted on the corpus passed to :meth:`fit`).  The fallback keeps the
    platform runnable on machines without PyTorch or internet access."""

    def __init__(self) -> None:
        self._model = None
        self._fallback = None
        self.backend = "uninitialised"

    def load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # lazy, optional
            logger.info("embeddings.loading", model=settings.embedding_model)
            self._model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
            self.backend = settings.embedding_model
            logger.info("embeddings.loaded")
        except Exception as exc:
            logger.warning("embeddings.fallback_tfidf_lsa", reason=str(exc)[:120])
            self._model = None
            self.backend = "tfidf-lsa"

    def fit(self, texts: list[str]) -> None:
        """Prepare the fallback encoder on the indexing corpus."""
        if self._model is None and self.backend != "tfidf-lsa":
            self.load()
        if self._model is None:
            from app.mimar.rankers import EmbeddingPairRanker
            r = EmbeddingPairRanker()
            r.fit(texts, [str(i) for i in range(len(texts))])
            self._fallback = r

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None and self.backend != "tfidf-lsa":
            self.load()
        if self._model is not None:
            return self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        if self._fallback is None:
            self.fit(texts)
        return np.asarray(self._fallback._encoder(texts), dtype="float32")

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


class FAISSVectorStore:
    """FAISS index with metadata sidecar for curriculum retrieval."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedder = embedding_service
        self._index: Any = None          # faiss.IndexFlatIP
        self._metadata: list[dict] = []  # parallel list aligned to index rows
        self._dim: int = 384             # MiniLM default

    def build(self, chunks: list[dict[str, Any]]) -> None:
        """Build index from a list of {id, content, source, source_type, metadata}."""
        if not FAISS_AVAILABLE:
            logger.warning("faiss.build_skipped")
            return

        texts = [c["content"] for c in chunks]
        self._embedder.fit(texts)
        embeddings = self._embedder.encode(texts).astype("float32")

        self._dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(self._dim)   # Inner-product on normalised → cosine
        self._index.add(embeddings)
        self._metadata = chunks

        logger.info("faiss.built", n_chunks=len(chunks), dim=self._dim)

    def save(self) -> None:
        if not self._index:
            return
        index_path = Path(settings.faiss_index_path)
        meta_path = Path(settings.faiss_metadata_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(index_path))
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)
        logger.info("faiss.saved", path=str(index_path))

    def load(self) -> bool:
        if not FAISS_AVAILABLE:
            return False
        index_path = Path(settings.faiss_index_path)
        meta_path = Path(settings.faiss_metadata_path)
        if not index_path.exists() or not meta_path.exists():
            logger.warning("faiss.index_not_found", path=str(index_path))
            return False

        self._index = faiss.read_index(str(index_path))
        with open(meta_path, encoding="utf-8") as f:
            self._metadata = json.load(f)
        # the fallback encoder is corpus-fitted and must be refitted on load
        self._embedder.fit([m["content"] for m in self._metadata])
        if self._embedder._model is None and self._index.d != self._embedder.encode(["x"]).shape[1]:
            logger.warning("faiss.dim_mismatch_rebuild")
            self.build(self._metadata)
        logger.info("faiss.loaded", n_chunks=len(self._metadata))
        return True

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not self._index or not FAISS_AVAILABLE:
            return []
        k = top_k or settings.rag_top_k_vector
        q_emb = self._embedder.encode_single(query).astype("float32").reshape(1, -1)
        scores, indices = self._index.search(q_emb, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = self._metadata[idx]
            results.append(RetrievedChunk(
                id=meta.get("id", str(idx)),
                content=meta["content"],
                source=meta.get("source", ""),
                source_type=meta.get("source_type", "block"),
                score=float(score),
                metadata=meta.get("metadata", {}),
            ))
        return results

    def is_ready(self) -> bool:
        return self._index is not None and len(self._metadata) > 0


# Singletons
embedding_service = EmbeddingService()
vector_store = FAISSVectorStore(embedding_service)
