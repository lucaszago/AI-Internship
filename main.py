"""Structured Q&A API with RAG ingest, retrieval debug, and same-origin web UI.

Run locally::

    uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Streamlit UI (calls this API)::

    uv run streamlit run ui/streamlit_app.py

On Databricks Apps the runtime calls ``python main.py``, which binds
``0.0.0.0:$PORT`` (Render) or ``0.0.0.0:$DATABRICKS_APP_PORT``.

API routes are mounted at ``/`` (browser UI, same-origin) and ``/api/``
(Databricks M2M token access — see README grader section).
"""

import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from rag.config import load_rag_config
from rag.routes import (
    AskResponse,
    AttemptResult,
    DebugRetrieveResponse,
    IngestRequest,
    IngestResponse,
    ModelName,
    DEFAULT_MODEL,
    compute_cost_usd,
    handle_debug_retrieve,
    handle_ingest,
    handle_rag_ask,
    usage_counts,
)

THIS_DIR = Path(__file__).resolve().parent
load_dotenv(THIS_DIR / ".env")
load_dotenv(THIS_DIR.parent / ".env")

app = FastAPI(
    title="Week 1 v2 /ask Demo",
    description=(
        "Session 2 RAG API. Browser UI at `/`. "
        "For programmatic access on Databricks Apps use `/api/*` with a Bearer token."
    ),
)
router = APIRouter()
_client: OpenAI | None = None

LIVE_APP_URL = "https://week1v2-ask-ui-299177927171866.aws.databricksapps.com"


class Answer(BaseModel):
    """Structured output schema for the Session 1 non-RAG guardrail demo."""

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sources_needed: bool


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    model: ModelName | None = None
    force_bad: bool = False


@router.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(THIS_DIR / "static" / "index.html")


@router.get("/health")
def health() -> dict[str, str | bool | dict[str, str | int]]:
    rag = load_rag_config()
    return {
        "status": "ok",
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "rag_configured": bool(rag.vector_search_index and rag.full_table_name),
        "rag": rag.to_dict(),
        "api_prefix": "/api",
        "live_url": LIVE_APP_URL,
    }


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def call_structured_model(question: str, model: ModelName) -> tuple[Answer, int, int, int]:
    completion = get_client().chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": question}],
        response_format=Answer,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model returned no parseable structured output")
    return parsed, *usage_counts(completion)


def call_malformed_json_once(question: str, model: ModelName) -> tuple[str, int, int, int]:
    completion = get_client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    "Reply with ONLY JSON using keys answer, confidence, sources_needed. "
                    "Set confidence to the string 'very high' instead of a number."
                ),
            }
        ],
    )
    raw = completion.choices[0].message.content or ""
    return raw, *usage_counts(completion)


@router.post("/ingest", response_model=IngestResponse)
def ingest(body: IngestRequest) -> IngestResponse:
    """Chunk, embed, write to Delta, and sync the AI Search index."""
    return handle_ingest(body)


@router.get("/debug/retrieve", response_model=DebugRetrieveResponse)
def debug_retrieve(q: str = Query(min_length=1)) -> DebugRetrieveResponse:
    """Return top-k chunks for a question without calling the LLM."""
    return handle_debug_retrieve(q)


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    """Answer using RAG (Databricks AI Search + grounded generation).

    When ``force_bad`` is true, runs the Session 1 guardrail demo without retrieval.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it as a Databricks App secret, or put it in local .env.",
        )

    model = body.model or DEFAULT_MODEL
    start = time.perf_counter()

    if not body.force_bad:
        try:
            return handle_rag_ask(get_client(), body.question, model, start)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"RAG response failed validation: {exc}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"RAG ask failed: {exc}",
            ) from exc

    last_error: str | None = None
    attempts: list[AttemptResult] = []
    total_tokens_used = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for attempt in range(2):
        try:
            if attempt == 0:
                raw, tokens_used, prompt_tokens, completion_tokens = call_malformed_json_once(
                    body.question, model
                )
                total_tokens_used += tokens_used
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                try:
                    answer = Answer.model_validate_json(raw)
                except ValidationError as exc:
                    last_error = str(exc)
                    attempts.append(
                        AttemptResult(
                            attempt=attempt + 1,
                            step="forced_bad_json",
                            ok=False,
                            message="Validation failed, so the endpoint retries with structured output.",
                            raw_output=raw,
                            validation_error=str(exc),
                        )
                    )
                    continue
                attempts.append(
                    AttemptResult(
                        attempt=attempt + 1,
                        step="forced_bad_json",
                        ok=True,
                        message="Unexpectedly passed validation.",
                        raw_output=raw,
                    )
                )
            else:
                answer, tokens_used, prompt_tokens, completion_tokens = call_structured_model(
                    body.question, model
                )
                total_tokens_used += tokens_used
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                attempts.append(
                    AttemptResult(
                        attempt=attempt + 1,
                        step="structured_output",
                        ok=True,
                        message="Structured output matched the Answer schema.",
                    )
                )

            return AskResponse(
                answer=answer.answer,
                tokens_used=total_tokens_used,
                cost_usd=round(
                    compute_cost_usd(model, total_prompt_tokens, total_completion_tokens), 6
                ),
                confidence_score=answer.confidence,
                sources_needed=answer.sources_needed,
                model=model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                attempts=attempts,
            )
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            attempts.append(
                AttemptResult(
                    attempt=attempt + 1,
                    step="structured_output",
                    ok=False,
                    message="Structured output failed validation.",
                    validation_error=str(exc),
                )
            )

    raise HTTPException(
        status_code=502,
        detail=f"Model response failed schema validation after retry: {last_error}",
    )


# Same routes at / and /api/* (Databricks M2M expects /api/ prefix).
app.include_router(router)
app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    port = int(
        os.environ.get("PORT", os.environ.get("DATABRICKS_APP_PORT", "8000"))
    )
    uvicorn.run(app, host="0.0.0.0", port=port)
