"""OpenAI embedding helpers shared by ingest and query."""

from __future__ import annotations

import os
from functools import lru_cache

from openai import OpenAI

from rag.config import load_rag_config


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def embed_texts(texts: list[str]) -> tuple[list[list[float]], int]:
    """Embed multiple texts; returns vectors and total embedding tokens used."""
    if not texts:
        return [], 0

    config = load_rag_config()
    response = get_openai_client().embeddings.create(
        model=config.embedding_model,
        input=texts,
    )
    vectors = [item.embedding for item in response.data]
    tokens = response.usage.total_tokens if response.usage else 0
    return vectors, tokens


def embed_query(question: str) -> tuple[list[float], int]:
    """Embed a single query string."""
    vectors, tokens = embed_texts([question])
    return vectors[0], tokens
