"""Databricks AI Search sync and similarity query."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from databricks.sdk import WorkspaceClient

from rag.config import load_rag_config

RETRIEVAL_COLUMNS = ["id", "document_id", "chunk_text", "source"]


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    document_id: str
    chunk_text: str
    source: str | None
    score: float | None


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    profile = os.getenv("DATABRICKS_CONFIG_PROFILE")
    if profile:
        return WorkspaceClient(profile=profile)
    return WorkspaceClient()


def top_k() -> int:
    return int(os.getenv("RAG_TOP_K", "5"))


def sync_index() -> None:
    config = load_rag_config()
    get_workspace_client().vector_search_indexes.sync_index(
        index_name=config.vector_search_index
    )


def _row_to_chunk(column_names: list[str], row: list) -> RetrievedChunk:
    values = dict(zip(column_names, row, strict=False))
    score = values.get("score")
    return RetrievedChunk(
        id=str(values.get("id", "")),
        document_id=str(values.get("document_id", "")),
        chunk_text=str(values.get("chunk_text", "")),
        source=values.get("source") if values.get("source") is not None else None,
        score=float(score) if score is not None else None,
    )


def query_chunks(query_vector: list[float], num_results: int | None = None) -> list[RetrievedChunk]:
    """Return top similar chunks for a query embedding."""
    config = load_rag_config()
    k = num_results or top_k()
    response = get_workspace_client().vector_search_indexes.query_index(
        index_name=config.vector_search_index,
        columns=RETRIEVAL_COLUMNS,
        query_vector=query_vector,
        num_results=k,
    )

    if not response.result or not response.result.data_array:
        return []

    column_names = [column.name for column in response.manifest.columns]
    return [_row_to_chunk(column_names, row) for row in response.result.data_array]
