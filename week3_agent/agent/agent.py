"""ADK ops revenue analyst — uses real ``run_sql`` tool on ``demo.db``.

Defines the Google ADK ``root_agent`` with instructions, model, and the
SELECT-only SQL tool. Import ``root_agent`` from runners; do not hardcode queries.
"""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import Agent

_AGENT_DIR = Path(__file__).resolve().parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from config import MODEL_NAME  # noqa: E402
from tools import run_sql  # noqa: E402

INSTRUCTION = """
You are an ops revenue analyst for a small retail/supplements business.

Use the run_sql tool for any numbers. Do not invent rows.
Only SELECT queries are allowed.

Schema:
- customers(id, name, city, created_at)
- products(id, name, category, price_usd)
- orders(id, customer_id, product_id, amount_usd, status, created_at)
  status: completed | cancelled | pending

Answer format:
1) KPI (the number)
2) Short insight
3) Optional next action

If the tool errors, fix the SQL and try again (within reason).
If data is insufficient, say so clearly.
""".strip()

# ADK auto-wraps plain Python functions as FunctionTools — no Tool(...) needed.
root_agent = Agent(
    name="ops_revenue_analyst",
    model=MODEL_NAME,
    description="Answers sales/ops KPI questions by querying the demo SQLite database.",
    instruction=INSTRUCTION,
    tools=[run_sql],
)


def main() -> None:
    """Print agent readiness (smoke check without calling Gemini)."""
    print("Agent ready:", root_agent.name)
    print(
        "Tools:",
        [getattr(t, "__name__", type(t).__name__) for t in (root_agent.tools or [])],
    )
    print("Next: uv run python week3_agent/agent/run_cli.py")


if __name__ == "__main__":
    main()
