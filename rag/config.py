"""RAG object names and settings loaded from environment variables.

Local development: set values in ``.env`` (see ``.env.example``).
Databricks Apps: ``databricks.yml`` / ``app.yaml`` inject env vars; the vector
search index name comes from the ``document_chunks_index`` app resource.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RagConfig:
    """Unity Catalog and AI Search names used by the RAG pipeline."""

    catalog: str
    schema: str
    table: str
    full_table_name: str
    vector_search_endpoint: str
    vector_search_index: str
    embedding_model: str
    embedding_dimensions: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "catalog": self.catalog,
            "schema": self.schema,
            "table": self.table,
            "full_table_name": self.full_table_name,
            "vector_search_endpoint": self.vector_search_endpoint,
            "vector_search_index": self.vector_search_index,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
        }

    @classmethod
    def from_env(cls) -> RagConfig:
        catalog = os.getenv("RAG_CATALOG", "workspace")
        schema = os.getenv("RAG_SCHEMA", "document_retrieval")
        table = os.getenv("RAG_TABLE", "document_chunks")
        default_index = f"{catalog}.{schema}.{table}_index"

        return cls(
            catalog=catalog,
            schema=schema,
            table=table,
            full_table_name=f"{catalog}.{schema}.{table}",
            vector_search_endpoint=os.getenv(
                "VECTOR_SEARCH_ENDPOINT", "document-chunks-search-endpoint"
            ),
            vector_search_index=os.getenv("VECTOR_SEARCH_INDEX", default_index),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
        )


def load_rag_config() -> RagConfig:
    """Return RAG settings from the current process environment."""
    return RagConfig.from_env()
