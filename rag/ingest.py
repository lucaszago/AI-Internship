"""End-to-end ingest: chunk, embed, write Delta, sync AI Search index."""

from __future__ import annotations

import logging

from rag.chunking import split_text
from rag.embeddings import embed_texts
from rag.search import sync_index
from rag.store import append_chunks, delete_document_chunks

logger = logging.getLogger(__name__)


def ingest_document(
    document_id: str,
    text: str,
    source: str | None = None,
    *,
    replace_existing: bool = True,
) -> tuple[int, int]:
    """Ingest plain text; returns ``(chunks_indexed, embedding_tokens)``.

    Delta write is required. Index sync is best-effort: app service principals
    often only have SELECT on AI Search indexes (MODIFY is not valid on
    TABLE_ONLINE_VECTOR_INDEX_REPLICA). If sync fails, rows are still in Delta —
    trigger sync as index owner, or transfer ownership to the app SP.
    """
    chunks = split_text(text)
    if not chunks:
        return 0, 0

    vectors, embedding_tokens = embed_texts(chunks)
    if replace_existing:
        delete_document_chunks(document_id)
    indexed = append_chunks(document_id, chunks, vectors, source=source)
    try:
        sync_index()
    except Exception as exc:
        logger.warning("Index sync skipped after Delta write: %s", exc)
    return indexed, embedding_tokens
