"""Pinecone similarity query."""

from __future__ import annotations

import os
from dataclasses import dataclass

from rag.store import get_pinecone_index

RETRIEVAL_METADATA = ("document_id", "chunk_text", "source")


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    document_id: str
    chunk_text: str
    source: str | None
    score: float | None


def top_k() -> int:
    return int(os.getenv("RAG_TOP_K", "5"))


def query_chunks(query_vector: list[float], num_results: int | None = None) -> list[RetrievedChunk]:
    """Return top similar chunks for a query embedding."""
    k = num_results or top_k()
    response = get_pinecone_index().query(
        vector=query_vector,
        top_k=k,
        include_metadata=True,
        namespace="",
    )

    matches = response.get("matches") or getattr(response, "matches", None) or []
    chunks: list[RetrievedChunk] = []
    for match in matches:
        metadata = match.get("metadata") if isinstance(match, dict) else (match.metadata or {})
        match_id = match.get("id") if isinstance(match, dict) else match.id
        score = match.get("score") if isinstance(match, dict) else match.score
        chunks.append(
            RetrievedChunk(
                id=str(match_id or ""),
                document_id=str(metadata.get("document_id", "")),
                chunk_text=str(metadata.get("chunk_text", "")),
                source=metadata.get("source"),
                score=float(score) if score is not None else None,
            )
        )
    return chunks
