# app/agent/agent.py

"""Custom AI Agent Harness for Kirana AI Agent with trusted execution context."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import time
from typing import Any, Dict, List, Optional

from app.agent.config import MAX_AGENT_ITERATIONS
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.schemas import AgentAction, AgentResponse
from app.auth.schemas import AuthenticatedPrincipal, ToolExecutionContext
from app.llm import LLMProvider, get_llm_provider
from app.tools import registry as default_registry
from app.tools.registry import ToolRegistry


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("app.agent")
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s: %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        os.makedirs("logs", exist_ok=True)
        fh = RotatingFileHandler("logs/agent.log", maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


logger = setup_logger()


class Agent:
    """Agent harness running the OBSERVE -> REASON -> ACT loop."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        llm_client: Optional[Any] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_iterations: int = MAX_AGENT_ITERATIONS,
    ) -> None:
        self.llm_provider = llm_provider or llm_client or get_llm_provider()
        self.llm_client = self.llm_provider
        self.registry = tool_registry or default_registry
        self.max_iterations = max_iterations

    def _build_system_prompt(self) -> str:
        tools_list = self.registry.list_tools()
        compact_tools = []
        for t in tools_list:
            schema = t.get("input_schema", {})
            properties = schema.get("properties", {})
            required_fields = set(schema.get("required", []))
            params = {}
            for k, v in properties.items():
                param_type = v.get("type", "any")
                if k in required_fields:
                    params[k] = f"{param_type} (REQUIRED)"
                else:
                    params[k] = f"{param_type} (optional)"

            compact_tools.append({
                "name": t["name"],
                "description": t["description"],
                "arguments": params,
            })
        tools_description = json.dumps(compact_tools, indent=2)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"AVAILABLE TOOLS:\n"
            f"{tools_description}\n\n"
            f"Remember: Respond ONLY with a valid JSON object matching the AgentAction schema."
        )
        return prompt

    def run(
        self,
        user_message: str,
        user_id: Optional[int] = None,
        context: Optional[ToolExecutionContext] = None,
    ) -> AgentResponse:
        """Run the agent loop for a user query with trusted execution context."""
        effective_user_id = user_id or (context.principal.user_id if context and context.principal else None)
        effective_store_id = context.principal.store_id if context and context.principal else 1

        if not context and effective_user_id:
            context = ToolExecutionContext(
                principal=AuthenticatedPrincipal(
                    user_id=effective_user_id,
                    store_id=effective_store_id,
                    role="OPERATOR",
                )
            )

        logger.info(f"--- Starting Agent Execution query: '{user_message}' (user_id={effective_user_id}, store_id={effective_store_id}) ---")
        system_prompt = self._build_system_prompt()

        session_history = load_session_history(effective_user_id, store_id=effective_store_id) if effective_user_id else []
        messages: List[Dict[str, str]] = list(session_history)
        messages.append({"role": "user", "content": user_message})

        tool_results: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Agent Loop Iteration {iteration}/{self.max_iterations}")
            start_time = time.time()

            try:
                action = self.llm_provider.generate_action(system_prompt, messages)
            except Exception as exc:
                elapsed = time.time() - start_time
                logger.error(f"LLM Client error on iteration {iteration} (latency {elapsed:.2f}s): {exc}")
                return AgentResponse(
                    content=f"Apologies, an error occurred while processing your request: {exc}",
                    metadata={"error": str(exc), "iteration": iteration, "tool_results": tool_results},
                )

            elapsed = time.time() - start_time
            logger.info(f"LLM Action Selected: '{action.action_type}' (latency {elapsed:.2f}s)")

            if action.action_type in {"final_response", "clarification"}:
                logger.info(f"--- Agent Completed successfully on iteration {iteration} ---")
                if effective_user_id:
                    session_history.append({"role": "user", "content": user_message})
                    session_history.append({"role": "assistant", "content": action.content or ""})
                    save_session_history(effective_user_id, session_history, store_id=effective_store_id)

                return AgentResponse(
                    content=action.content or "",
                    metadata={"iterations": iteration, "action_type": action.action_type, "tool_results": tool_results},
                )

            if action.action_type == "tool_call":
                tool_name = action.tool_name or ""
                arguments = action.arguments or {}
                logger.info(f"Executing Tool '{tool_name}' with arguments: {arguments}")

                tool_start = time.time()
                tool_result = self.registry.execute(tool_name, arguments, context=context)
                tool_elapsed = time.time() - tool_start

                if tool_result.success:
                    logger.info(f"Tool '{tool_name}' executed successfully (latency {tool_elapsed:.2f}s)")
                    obs_payload = json.dumps({"success": True, "data": tool_result.data}, default=str)
                    tool_results.append({"tool_name": tool_name, "data": tool_result.data})
                else:
                    err_msg = tool_result.error.message if tool_result.error else "Unknown tool error"
                    err_code = tool_result.error.code if tool_result.error else "TOOL_ERROR"
                    logger.warning(f"Tool '{tool_name}' failed [{err_code}]: {err_msg}")
                    obs_payload = json.dumps({"success": False, "error": {"code": err_code, "message": err_msg}}, default=str)

                messages.append({"role": "assistant", "content": action.model_dump_json()})
                messages.append({"role": "user", "content": f"Observation for tool '{tool_name}': {obs_payload}"})

        logger.warning(f"Reached maximum iterations ({self.max_iterations}) without final answer.")
        return AgentResponse(
            content="I am unable to complete your request within the maximum allowed steps. Please try simplifying your request.",
            metadata={"iterations": self.max_iterations, "status": "MAX_ITERATIONS_EXCEEDED", "tool_results": tool_results},
        )


def load_session_history(user_id: int, store_id: int = 1) -> List[Dict[str, str]]:
    """Load conversation history for a user ID and store ID from AgentSession table."""
    from app.db.database import get_db_context
    from app.db.models import AgentSession

    if not user_id:
        return []
    try:
        with get_db_context() as db:
            session_rec = db.query(AgentSession).filter(
                AgentSession.store_id == store_id,
                AgentSession.user_id == user_id,
            ).first()
            if session_rec and session_rec.history_json:
                return json.loads(session_rec.history_json)
    except Exception as exc:
        logger.warning(f"Failed to load session history for user_id {user_id}: {exc}")
    return []


def save_session_history(user_id: int, history: List[Dict[str, str]], store_id: int = 1, max_turns: int = 12) -> None:
    """Save conversation history for a user ID and store ID into AgentSession table."""
    from app.db.database import get_db_context
    from app.db.models import AgentSession

    if not user_id:
        return
    try:
        trimmed = history[-max_turns:]
        with get_db_context() as db:
            session_rec = db.query(AgentSession).filter(
                AgentSession.store_id == store_id,
                AgentSession.user_id == user_id,
            ).first()
            if not session_rec:
                session_rec = AgentSession(store_id=store_id, user_id=user_id, history_json=json.dumps(trimmed))
                db.add(session_rec)
            else:
                session_rec.history_json = json.dumps(trimmed)
            db.commit()
    except Exception as exc:
        logger.warning(f"Failed to save session history for user_id {user_id}: {exc}")


def clear_session_history(user_id: int, store_id: int = 1) -> bool:
    """Clear conversation history for a user ID and store ID from AgentSession table."""
    from app.db.database import get_db_context
    from app.db.models import AgentSession

    try:
        with get_db_context() as db:
            session_rec = db.query(AgentSession).filter(
                AgentSession.store_id == store_id,
                AgentSession.user_id == user_id,
            ).first()
            if session_rec:
                db.delete(session_rec)
                db.commit()
            return True
    except Exception as exc:
        logger.error(f"Failed to clear session history for user_id {user_id}: {exc}")
        return False
