"""Upsert and delete document chunks in Pinecone."""

from __future__ import annotations

from functools import lru_cache

from pinecone import Pinecone
from pinecone.exceptions import NotFoundException, PineconeApiException

from rag.config import load_rag_config

# Default namespace — empty string is Pinecone's standard default.
NAMESPACE = ""


@lru_cache(maxsize=1)
def get_pinecone_index():
    """Return a Pinecone Index client."""
    config = load_rag_config()
    if not config.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is not set.")
    client = Pinecone(api_key=config.pinecone_api_key)
    return client.index(name=config.pinecone_index)


def delete_document_chunks(document_id: str) -> None:
    """Remove existing vectors for ``document_id`` before re-ingest.

    An empty index has no namespace yet, so Pinecone may return 404 on delete.
    That is safe to ignore on first ingest.
    """
    index = get_pinecone_index()
    try:
        index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=NAMESPACE,
        )
    except NotFoundException:
        return
    except PineconeApiException as exc:
        # Serverless: "[404] Namespace not found" on first write.
        if getattr(exc, "status", None) == 404 or "Namespace not found" in str(exc):
            return
        raise


def append_chunks(
    document_id: str,
    chunks: list[str],
    vectors: list[list[float]],
    source: str | None = None,
) -> int:
    """Upsert chunked rows with embeddings into Pinecone."""
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")

    if not chunks:
        return 0

    records = []
    for chunk_index, (chunk_text, vector) in enumerate(zip(chunks, vectors, strict=True)):
        metadata: dict[str, str | int] = {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
        }
        if source:
            metadata["source"] = source
        records.append(
            {
                "id": f"{document_id}::{chunk_index}",
                "values": vector,
                "metadata": metadata,
            }
        )

    get_pinecone_index().upsert(vectors=records, namespace=NAMESPACE)
    return len(records)
