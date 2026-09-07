"""Pydantic schemas for ``POST /agent``."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentStepOut(BaseModel):
    """One Think / Act / Observe step returned to the client."""

    label: str = Field(description="Think | Act | Observe")
    detail: str


class AgentRequest(BaseModel):
    """Body for ``POST /agent``."""

    question: str = Field(min_length=1, description="Manager / ops question")


class AgentResponse(BaseModel):
    """Final KPI brief plus labeled agent loop steps."""

    question: str
    answer: str
    steps: list[AgentStepOut]
