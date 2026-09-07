"""Streamlit UI for the Week 3 ops revenue analyst agent (Path A demo)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from session_runner import run_agent  # noqa: E402

DEFAULT_QUESTION = (
    "Which city has the highest total completed-order revenue?"
)


def main() -> None:
    """Render the Streamlit page: question → steps → final KPI brief."""
    st.set_page_config(page_title="Ops revenue analyst", layout="wide")
    st.title("Ops revenue analyst")
    st.caption(
        "Week 3 ADK agent — asks a business question, runs real SQL via `run_sql`, "
        "and shows Think → Act → Observe."
    )

    with st.sidebar:
        st.header("About")
        st.markdown(
            "This is an **agent** because it chooses and revises SQL based on "
            "tool results, not a fixed query script."
        )
        st.markdown("Requires `GOOGLE_API_KEY` in `week3_agent/.env`.")
        st.markdown(
            "Seed DB first:\n\n"
            "`uv run python week3_agent/agent/seed_demo_db.py`"
        )

    question = st.text_area(
        "Manager question",
        value=DEFAULT_QUESTION,
        height=100,
    )
    run = st.button("Run agent", type="primary")

    if not run:
        st.info("Enter a question and click **Run agent**.")
        return

    if not question.strip():
        st.error("Please enter a question.")
        return

    with st.spinner("Agent running (Think → Act → Observe)…"):
        try:
            result = run_agent(question.strip())
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    st.subheader("Think → Act → Observe")
    if not result.steps:
        st.warning("No steps were recorded for this run.")
    for step in result.steps:
        st.markdown(f"**[{step.label}]** {step.detail}")

    st.subheader("Final answer")
    st.write(result.final_answer)

    with st.expander("Raw step list"):
        st.json(
            [{"label": s.label, "detail": s.detail} for s in result.steps]
        )


if __name__ == "__main__":
    main()
