"""RAG settings loaded from environment variables (Pinecone + OpenAI)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RagConfig:
    """Pinecone index and embedding settings used by the RAG pipeline."""

    pinecone_api_key: str
    pinecone_index: str
    embedding_model: str
    embedding_dimensions: int

    def to_dict(self) -> dict[str, str | int | bool]:
        return {
            "pinecone_index": self.pinecone_index,
            "pinecone_configured": bool(self.pinecone_api_key),
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
        }

    @classmethod
    def from_env(cls) -> RagConfig:
        return cls(
            pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
            pinecone_index=os.getenv("PINECONE_INDEX_NAME", "document-chunks"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
        )


def load_rag_config() -> RagConfig:
    """Return RAG settings from the current process environment."""
    return RagConfig.from_env()
