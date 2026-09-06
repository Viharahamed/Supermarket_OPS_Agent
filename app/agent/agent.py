# app/agent/agent.py

"""Custom AI Agent Harness for Kirana AI Agent.

Implements the OBSERVE -> REASON -> ACT execution loop using Gemma 2 via Ollama
and the Phase 9 ToolRegistry.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import time
from typing import Any, Dict, List, Optional

from app.agent.config import MAX_AGENT_ITERATIONS
from app.agent.ollama_client import OllamaClient
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.schemas import AgentAction, AgentResponse
from app.tools import registry as default_registry
from app.tools.registry import ToolRegistry


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("app.agent")
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s: %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Rotating file handler at logs/agent.log
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
        llm_client: Optional[OllamaClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_iterations: int = MAX_AGENT_ITERATIONS,
    ) -> None:
        self.llm_client = llm_client or OllamaClient()
        self.registry = tool_registry or default_registry
        self.max_iterations = max_iterations

    def _build_system_prompt(self) -> str:
        tools_list = self.registry.list_tools()
        compact_tools = []
        for t in tools_list:
            schema = t.get("input_schema", {})
            properties = schema.get("properties", {})
            params = {k: v.get("type", "any") for k, v in properties.items()}
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

    def run(self, user_message: str) -> AgentResponse:
        """Run the agent loop for a user query."""
        logger.info(f"--- Starting Agent Execution for query: '{user_message}' ---")
        system_prompt = self._build_system_prompt()
        messages: List[Dict[str, str]] = [{"role": "user", "content": user_message}]

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Agent Loop Iteration {iteration}/{self.max_iterations}")
            start_time = time.time()

            try:
                action = self.llm_client.generate_action(system_prompt, messages)
            except Exception as exc:
                elapsed = time.time() - start_time
                logger.error(f"LLM Client error on iteration {iteration} (latency {elapsed:.2f}s): {exc}")
                return AgentResponse(
                    content=f"Apologies, an error occurred while processing your request: {exc}",
                    metadata={"error": str(exc), "iteration": iteration},
                )

            elapsed = time.time() - start_time
            logger.info(f"LLM Action Selected: '{action.action_type}' (latency {elapsed:.2f}s)")

            if action.action_type in {"final_response", "clarification"}:
                logger.info(f"--- Agent Completed successfully on iteration {iteration} ---")
                return AgentResponse(
                    content=action.content or "",
                    metadata={"iterations": iteration, "action_type": action.action_type},
                )

            if action.action_type == "tool_call":
                tool_name = action.tool_name or ""
                arguments = action.arguments or {}
                logger.info(f"Executing Tool '{tool_name}' with arguments: {arguments}")

                tool_start = time.time()
                tool_result = self.registry.execute(tool_name, arguments)
                tool_elapsed = time.time() - tool_start

                if tool_result.success:
                    logger.info(f"Tool '{tool_name}' executed successfully (latency {tool_elapsed:.2f}s)")
                    obs_payload = json.dumps({"success": True, "data": tool_result.data}, default=str)
                else:
                    err_msg = tool_result.error.message if tool_result.error else "Unknown tool error"
                    err_code = tool_result.error.code if tool_result.error else "TOOL_ERROR"
                    logger.warning(f"Tool '{tool_name}' failed [{err_code}]: {err_msg}")
                    obs_payload = json.dumps({"success": False, "error": {"code": err_code, "message": err_msg}}, default=str)

                # Record assistant action & tool observation in message history
                messages.append({"role": "assistant", "content": action.model_dump_json()})
                messages.append({"role": "user", "content": f"Observation for tool '{tool_name}': {obs_payload}"})

        logger.warning(f"Reached maximum iterations ({self.max_iterations}) without final answer.")
        return AgentResponse(
            content="I am unable to complete your request within the maximum allowed steps. Please try simplifying your request.",
            metadata={"iterations": self.max_iterations, "status": "MAX_ITERATIONS_EXCEEDED"},
        )


def clear_session_history(user_id: int) -> bool:
    """Clear conversation history for a given user ID from AgentSession table.

    Does NOT touch products, bills, stock, customers, Khata, or store preferences.
    """
    from app.db.database import get_db_context
    from app.db.models import AgentSession

    try:
        with get_db_context() as db:
            session_rec = db.query(AgentSession).filter(AgentSession.user_id == user_id).first()
            if session_rec:
                db.delete(session_rec)
                db.commit()
            return True
    except Exception as exc:
        logger.error(f"Failed to clear session history for user_id {user_id}: {exc}")
        return False
