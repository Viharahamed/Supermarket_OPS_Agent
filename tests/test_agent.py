from unittest.mock import MagicMock

import pytest

from app.agent.agent import Agent
from app.agent.schemas import AgentAction, AgentResponse
from app.exceptions import (
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from app.tools.registry import ToolRegistry


def test_agent_action_validation():
    # Valid tool_call
    action = AgentAction(
        action_type="tool_call",
        tool_name="search_products",
        arguments={"query": "rice"},
    )
    assert action.action_type == "tool_call"
    assert action.tool_name == "search_products"

    # Valid final_response
    action_final = AgentAction(
        action_type="final_response",
        content="Stock is 50 kg.",
    )
    assert action_final.content == "Stock is 50 kg."

    # Invalid action_type
    with pytest.raises(ValueError):
        AgentAction(action_type="invalid_type")

    # Missing tool_name for tool_call
    with pytest.raises(ValueError):
        AgentAction(action_type="tool_call", arguments={"query": "rice"})


def test_agent_run_single_step_final_response():
    mock_llm = MagicMock()
    mock_llm.generate_action.return_value = AgentAction(
        action_type="final_response",
        content="Hello! How can I help you today?",
    )

    agent = Agent(llm_client=mock_llm, max_iterations=8)
    response = agent.run("Hello")

    assert isinstance(response, AgentResponse)
    assert response.content == "Hello! How can I help you today?"
    assert response.metadata["iterations"] == 1


def test_agent_run_multi_step_tool_execution():
    mock_llm = MagicMock()

    # Iteration 1: Call search_products tool
    # Iteration 2: Return final answer based on tool result
    mock_llm.generate_action.side_effect = [
        AgentAction(
            action_type="tool_call",
            tool_name="search_products",
            arguments={"query": "Milk"},
        ),
        AgentAction(
            action_type="final_response",
            content="Found Amul Taaza Milk in inventory.",
        ),
    ]

    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = []
    mock_registry.execute.return_value = MagicMock(
        success=True,
        data=[{"name": "Amul Taaza Milk", "stock_quantity": 20}],
    )

    agent = Agent(llm_client=mock_llm, tool_registry=mock_registry, max_iterations=8)
    response = agent.run("Find Milk in stock")

    assert response.content == "Found Amul Taaza Milk in inventory."
    assert response.metadata["iterations"] == 2
    mock_registry.execute.assert_called_once_with("search_products", {"query": "Milk"})


def test_agent_run_iteration_cap():
    mock_llm = MagicMock()
    # Always return tool call, never final_response
    mock_llm.generate_action.return_value = AgentAction(
        action_type="tool_call",
        tool_name="get_low_stock",
        arguments={},
    )

    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = []
    mock_registry.execute.return_value = MagicMock(success=True, data=[])

    agent = Agent(llm_client=mock_llm, tool_registry=mock_registry, max_iterations=3)
    response = agent.run("Loop forever")

    assert response.metadata["status"] == "MAX_ITERATIONS_EXCEEDED"
    assert response.metadata["iterations"] == 3


def test_agent_handles_llm_exceptions():
    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = OllamaUnavailableError("Service down")

    agent = Agent(llm_client=mock_llm)
    response = agent.run("Check stock")

    assert "Service down" in response.content
    assert "error" in response.metadata
