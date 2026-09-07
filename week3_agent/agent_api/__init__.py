"""HTTP bridge: FastAPI ↔ Week 3 ADK ops revenue analyst."""

from week3_agent.agent_api.routes import router as agent_router

__all__ = ["agent_router"]
