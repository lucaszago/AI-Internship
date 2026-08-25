"""Split documents into overlapping chunks for embedding."""

from __future__ import annotations

import os

from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_size() -> int:
    return int(os.getenv("RAG_CHUNK_SIZE", "800"))


def chunk_overlap() -> int:
    return int(os.getenv("RAG_CHUNK_OVERLAP", "100"))


def split_text(text: str) -> list[str]:
    """Split ``text`` into retrieval-sized chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size(),
        chunk_overlap=chunk_overlap(),
    )
    chunks = [part.strip() for part in splitter.split_text(text) if part.strip()]
    return chunks
