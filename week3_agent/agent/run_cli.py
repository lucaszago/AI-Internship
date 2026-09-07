"""CLI entrypoint: prove Think → Act → Observe for Path A."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from session_runner import run_agent  # noqa: E402

DEFAULT_QUESTION = (
    "Which city has the highest total completed-order revenue?"
)


def main(argv: list[str] | None = None) -> int:
    """Run one agent question and print a labeled trace to the console.

    Args:
        argv: Optional CLI args (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 1 on failure).
    """
    parser = argparse.ArgumentParser(
        description="Week 3 ops revenue analyst — CLI Think/Act/Observe proof",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=DEFAULT_QUESTION,
        help="Business question to ask the agent",
    )
    args = parser.parse_args(argv)

    print(f"Question: {args.question}\n", flush=True)
    try:
        result = run_agent(args.question)
    except Exception as exc:  # noqa: BLE001 — show clear CLI errors
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1

    print("=== Think → Act → Observe ===")
    for index, step in enumerate(result.steps, start=1):
        print(f"{index}. [{step.label}] {step.detail}")
    print("\n=== Final answer ===")
    print(result.final_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
