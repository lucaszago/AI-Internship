"""FastAPI routes that invoke the Week 3 ADK agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from week3_agent.agent_api.schemas import AgentRequest, AgentResponse, AgentStepOut

# session_runner / tools use flat imports (config, agent) — match CLI/UI path setup
_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from session_runner import run_agent_async  # noqa: E402

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/health")
def agent_health() -> dict[str, str | bool]:
    """Lightweight check that the agent route is mounted and key is present."""
    return {
        "status": "ok",
        "google_key_configured": bool(os.getenv("GOOGLE_API_KEY", "").strip()),
    }


@router.post("", response_model=AgentResponse)
async def run_ops_agent(body: AgentRequest) -> AgentResponse:
    """Run the ops revenue analyst and return Think → Act → Observe + answer."""
    try:
        result = await run_agent_async(body.question.strip())
    except RuntimeError as exc:
        # Missing GOOGLE_API_KEY / clear setup errors
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface model/tool failures without secrets
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AgentResponse(
        question=result.question,
        answer=result.final_answer,
        steps=[
            AgentStepOut(label=step.label, detail=step.detail) for step in result.steps
        ],
    )
