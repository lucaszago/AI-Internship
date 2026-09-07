"""Shared settings for the Week 3 ops revenue analyst agent.

Loads ``week3_agent/.env`` (then repo-root ``.env`` without overriding) and
exposes paths, model name, and loop bounds used by tools, ADK agent, and runners.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# week3_agent/agent/config.py -> week3_agent/
WEEK3_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = WEEK3_ROOT.parent

# Load week3 .env first, then repo-root .env (without overriding)
load_dotenv(WEEK3_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

DEFAULT_DB_PATH = WEEK3_ROOT / "data" / "demo.db"


def _resolve_db_path() -> Path:
    """Resolve ``DB_PATH`` relative to ``week3_agent/`` or the repo root.

    Returns:
        Absolute path to the SQLite database file.
    """
    raw = os.getenv("DB_PATH", "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    # Prefer paths relative to week3_agent/ (e.g. ./data/demo.db)
    candidate = (WEEK3_ROOT / path).resolve()
    if candidate.exists() or path.parts[0] in (".", "data"):
        return candidate
    # Fallback: relative to repo root (e.g. week3_agent/data/demo.db)
    return (REPO_ROOT / path).resolve()


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
DB_PATH = _resolve_db_path()
AGENT_MAX_STEPS = int(
    os.getenv("AGENT_MAX_STEPS") or os.getenv("AGENT_MAX_STEP") or "8"
)
MAX_ROWS = int(os.getenv("AGENT_MAX_ROWS", "50"))
MODEL_NAME = os.getenv("AGENT_MODEL", "gemini-3.6-flash")


def require_google_api_key() -> str:
    """Return the Gemini API key or raise a clear setup error.

    Returns:
        Non-empty ``GOOGLE_API_KEY`` value.

    Raises:
        RuntimeError: If the key is missing from the environment / ``.env``.
    """
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. "
            "Copy week3_agent/.env.example to week3_agent/.env and add your key."
        )
    return GOOGLE_API_KEY
