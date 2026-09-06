from typing import Optional
from app.agent.agent import Agent, clear_session_history
from app.agent.schemas import AgentResponse


def handle_message(message: str, user_id: Optional[int] = None) -> AgentResponse:
    """Entry point for handling a user message.

    Returns an ``AgentResponse`` defined in ``app.agent.schemas``.
    """
    agent = Agent()
    return agent.run(message)


def clear_session(user_id: int) -> bool:
    """Clear conversational history for a user ID without touching database entities."""
    return clear_session_history(user_id)


__all__ = ["Agent", "handle_message", "clear_session", "AgentResponse"]
