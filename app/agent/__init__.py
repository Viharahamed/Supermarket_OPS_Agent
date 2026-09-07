from typing import Optional
from app.agent.agent import Agent, clear_session_history
from app.agent.schemas import AgentResponse
from app.auth.schemas import ToolExecutionContext


def handle_message(
    message: str,
    user_id: Optional[int] = None,
    context: Optional[ToolExecutionContext] = None,
) -> AgentResponse:
    """Entry point for handling a user message with optional trusted execution context."""
    agent = Agent()
    return agent.run(message, user_id=user_id, context=context)


def clear_session(user_id: int, store_id: int = 1) -> bool:
    """Clear conversational history for a user ID and store ID."""
    return clear_session_history(user_id, store_id=store_id)


__all__ = ["Agent", "handle_message", "clear_session", "AgentResponse"]
