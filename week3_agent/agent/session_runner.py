"""Shared ADK runner that labels Think → Act → Observe for CLI and Streamlit."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from config import AGENT_MAX_STEPS, require_google_api_key
from agent import root_agent


@dataclass
class AgentStep:
    """One labeled step in the agent loop for Maven / UI display."""

    label: str
    detail: str


@dataclass
class AgentRunResult:
    """Final answer plus the Think → Act → Observe trace."""

    question: str
    final_answer: str
    steps: list[AgentStep] = field(default_factory=list)


def _part_text(part: Any) -> str:
    """Extract plain text from a genai Part if present."""
    text = getattr(part, "text", None)
    return text.strip() if isinstance(text, str) and text.strip() else ""


def _format_tool_args(args: Any) -> str:
    """Compact string for tool arguments."""
    if args is None:
        return ""
    if isinstance(args, dict):
        sql = args.get("sql") or args.get("query")
        if isinstance(sql, str):
            return sql.strip()
        return str(args)
    return str(args)


def _format_tool_response(response: Any) -> str:
    """Compact observation text from a function response."""
    if response is None:
        return ""
    if isinstance(response, dict):
        status = response.get("status")
        if status == "error":
            return f"error: {response.get('message')}"
        if status == "ok":
            cols = response.get("columns")
            rows = response.get("rows")
            count = response.get("row_count")
            return f"columns={cols} row_count={count} rows={rows}"
    return str(response)[:2000]


async def run_agent_async(question: str) -> AgentRunResult:
    """Run the ops analyst once and collect Think / Act / Observe steps.

    Args:
        question: Natural-language business question from a manager.

    Returns:
        AgentRunResult with final_answer and ordered labeled steps.
    """
    api_key = require_google_api_key()
    os.environ["GOOGLE_API_KEY"] = api_key

    session_service = InMemorySessionService()
    app_name = "week3_ops_revenue_analyst"
    user_id = "local-user"
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=str(uuid.uuid4()),
    )

    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=session_service,
    )
    run_config = RunConfig(max_llm_calls=AGENT_MAX_STEPS)

    steps: list[AgentStep] = []
    final_chunks: list[str] = []

    new_message = types.Content(
        role="user",
        parts=[types.Part(text=question)],
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=new_message,
        run_config=run_config,
    ):
        # Think / Act: model requested tool(s)
        for call in event.get_function_calls() or []:
            name = getattr(call, "name", "tool")
            args = getattr(call, "args", None) or getattr(call, "arguments", None)
            steps.append(
                AgentStep(
                    label="Think",
                    detail=f"Model chose tool `{name}`",
                )
            )
            steps.append(
                AgentStep(
                    label="Act",
                    detail=f"{name}({_format_tool_args(args)})",
                )
            )

        # Observe: tool returned data
        for response in event.get_function_responses() or []:
            name = getattr(response, "name", "tool")
            payload = getattr(response, "response", None)
            if payload is None:
                payload = getattr(response, "result", None)
            steps.append(
                AgentStep(
                    label="Observe",
                    detail=f"{name} → {_format_tool_response(payload)}",
                )
            )

        # Model text (reasoning or final answer)
        content = getattr(event, "content", None)
        if content and getattr(content, "parts", None):
            for part in content.parts:
                text = _part_text(part)
                if not text:
                    continue
                # Skip pure function-call parts that also carry empty text
                if event.get_function_calls():
                    continue
                if event.get_function_responses():
                    continue
                steps.append(AgentStep(label="Think", detail=text[:1500]))
                final_chunks.append(text)

    final_answer = final_chunks[-1] if final_chunks else "(no final text returned)"
    return AgentRunResult(question=question, final_answer=final_answer, steps=steps)


def run_agent(question: str) -> AgentRunResult:
    """Synchronous wrapper around :func:`run_agent_async`."""
    import asyncio

    return asyncio.run(run_agent_async(question))
