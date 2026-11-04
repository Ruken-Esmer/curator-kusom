"""
CURATOR — BM25 Keyword Retriever
Complements vector search with exact-term matching.
"""
from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.core.logging import logger
from app.models.schemas import RetrievedChunk

settings = get_settings()


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-zçğıöşüa-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


class BM25Retriever:
    """Thin wrapper around rank-bm25 with the same interface as FAISSVectorStore."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict[str, Any]] = []

    def build(self, chunks: list[dict[str, Any]]) -> None:
        self._corpus = chunks
        tokenized = [_tokenize(c["content"]) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        logger.info("bm25.built", n_chunks=len(chunks))

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not self._bm25:
            return []
        k = top_k or settings.rag_top_k_bm25
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            meta = self._corpus[idx]
            results.append(RetrievedChunk(
                id=meta.get("id", str(idx)),
                content=meta["content"],
                source=meta.get("source", ""),
                source_type=meta.get("source_type", "block"),
                score=float(scores[idx]),
                metadata=meta.get("metadata", {}),
            ))
        return results

    def is_ready(self) -> bool:
        return self._bm25 is not None


bm25_retriever = BM25Retriever()
