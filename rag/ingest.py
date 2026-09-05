"""End-to-end ingest: chunk, embed, upsert into Pinecone."""

from __future__ import annotations

from rag.chunking import split_text
from rag.embeddings import embed_texts
from rag.store import append_chunks, delete_document_chunks


def ingest_document(
    document_id: str,
    text: str,
    source: str | None = None,
    *,
    replace_existing: bool = True,
) -> tuple[int, int]:
    """Ingest plain text; returns ``(chunks_indexed, embedding_tokens)``."""
    chunks = split_text(text)
    if not chunks:
        return 0, 0

    vectors, embedding_tokens = embed_texts(chunks)
    if replace_existing:
        delete_document_chunks(document_id)
    indexed = append_chunks(document_id, chunks, vectors, source=source)
    return indexed, embedding_tokens
