"""Grounding prompts for retrieval-augmented generation."""

from __future__ import annotations

from rag.search import RetrievedChunk

REFUSAL_PHRASE = "I don't have enough information to answer that."


def format_context(chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = []
    for chunk in chunks:
        lines.append(
            f"[chunk_id={chunk.id} document_id={chunk.document_id}]\n{chunk.chunk_text}"
        )
    return "\n\n".join(lines)


def build_grounding_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Build a prompt that constrains the model to retrieved context only."""
    context = format_context(chunks) if chunks else "(no context retrieved)"
    return f"""Answer using ONLY the context below.
If the context does not contain the answer, respond with exactly:
"{REFUSAL_PHRASE}"
When you answer from the context:
- put each chunk's document_id in cited_document_ids
- put each chunk's chunk_id in cited_chunk_ids (from the [chunk_id=...] labels)
Set sources_needed to true when you used context chunks, false when refusing.

Context:
{context}

Question: {question}"""
