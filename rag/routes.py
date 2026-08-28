"""Session 2 RAG routes and schemas for the FastAPI app."""

from __future__ import annotations

import os
import time
from typing import Literal

from fastapi import HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from rag.embeddings import embed_query
from rag.ingest import ingest_document
from rag.prompts import REFUSAL_PHRASE, build_grounding_prompt
from rag.search import RetrievedChunk, query_chunks

ModelName = Literal["gpt-4o-mini", "gpt-4o", "o3-mini"]
DEFAULT_MODEL: ModelName = "gpt-4o-mini"
MODEL_PRICES_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "o3-mini": (0.0011, 0.0044),
}


class IngestRequest(BaseModel):
    text: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    source: str | None = None


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    status: str


class RetrievedChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_text: str
    source: str | None = None
    score: float | None = None


class DebugRetrieveResponse(BaseModel):
    question: str
    chunks: list[RetrievedChunkResponse]


class RagAnswer(BaseModel):
    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sources_needed: bool
    cited_document_ids: list[str] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)


class AttemptResult(BaseModel):
    attempt: int
    step: str
    ok: bool
    message: str
    raw_output: str | None = None
    validation_error: str | None = None


class AskResponse(BaseModel):
    answer: str
    tokens_used: int
    cost_usd: float
    confidence_score: float = Field(ge=0.0, le=1.0)
    sources_needed: bool
    model: str
    latency_ms: int
    attempts: list[AttemptResult]
    citations: list[str] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    refused: bool = False


def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_per_1k, output_per_1k = MODEL_PRICES_PER_1K.get(
        model, MODEL_PRICES_PER_1K[DEFAULT_MODEL]
    )
    return (prompt_tokens / 1000 * input_per_1k) + (
        completion_tokens / 1000 * output_per_1k
    )


def usage_counts(completion) -> tuple[int, int, int]:
    usage = completion.usage
    if usage is None:
        return 0, 0, 0
    return usage.total_tokens, usage.prompt_tokens, usage.completion_tokens


def chunk_to_response(chunk: RetrievedChunk) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_text=chunk.chunk_text,
        source=chunk.source,
        score=chunk.score,
    )


def require_openai_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it as a Databricks App secret, or put it in local .env.",
        )


def handle_ingest(body: IngestRequest) -> IngestResponse:
    require_openai_key()
    try:
        chunks_indexed, _ = ingest_document(
            document_id=body.document_id,
            text=body.text,
            source=body.source,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ingest failed: {exc}",
        ) from exc

    if chunks_indexed == 0:
        raise HTTPException(status_code=400, detail="No chunks produced from input text.")

    return IngestResponse(
        document_id=body.document_id,
        chunks_indexed=chunks_indexed,
        status="indexed",
    )


def handle_debug_retrieve(question: str) -> DebugRetrieveResponse:
    require_openai_key()
    try:
        query_vector, _ = embed_query(question)
        chunks = query_chunks(query_vector)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Retrieval failed: {exc}",
        ) from exc

    return DebugRetrieveResponse(
        question=question,
        chunks=[chunk_to_response(chunk) for chunk in chunks],
    )


def call_rag_structured_model(
    client: OpenAI,
    prompt: str,
    model: ModelName,
) -> tuple[RagAnswer, int, int, int]:
    completion = client.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=RagAnswer,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model returned no parseable structured output")
    return parsed, *usage_counts(completion)


def is_refusal(answer: str) -> bool:
    return REFUSAL_PHRASE.lower() in answer.lower()


def handle_rag_ask(
    client: OpenAI,
    question: str,
    model: ModelName,
    start: float,
) -> AskResponse:
    query_vector, embed_tokens = embed_query(question)
    chunks = query_chunks(query_vector)
    retrieved_chunk_ids = [chunk.id for chunk in chunks]
    prompt = build_grounding_prompt(question, chunks)

    answer, total_tokens, prompt_tokens, completion_tokens = call_rag_structured_model(
        client, prompt, model
    )
    total_tokens += embed_tokens

    citations = list(dict.fromkeys(answer.cited_document_ids))
    cited_chunk_ids = list(dict.fromkeys(answer.cited_chunk_ids))
    if not cited_chunk_ids and citations and retrieved_chunk_ids:
        cited_chunk_ids = [
            chunk_id
            for chunk_id in retrieved_chunk_ids
            if any(chunk_id.startswith(f"{doc_id}::") for doc_id in citations)
        ]
    refused = is_refusal(answer.answer)

    return AskResponse(
        answer=answer.answer,
        tokens_used=total_tokens,
        cost_usd=round(compute_cost_usd(model, prompt_tokens, completion_tokens), 6),
        confidence_score=answer.confidence,
        sources_needed=answer.sources_needed,
        model=model,
        latency_ms=int((time.perf_counter() - start) * 1000),
        attempts=[
            AttemptResult(
                attempt=1,
                step="rag_structured_output",
                ok=True,
                message=f"Retrieved {len(chunks)} chunks from Databricks AI Search.",
            )
        ],
        citations=citations,
        cited_chunk_ids=cited_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        refused=refused,
    )
