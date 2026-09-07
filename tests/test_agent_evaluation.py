# tests/test_agent_evaluation.py

"""Comprehensive AI Agent Implementation Evaluation Test Suite.

Tests the AI Agent implementation across 9 core dimensions:
1. AgentAction Pydantic schema validation & strict guards.
2. Dynamic system prompt construction & Tool Registry schema injection.
3. Single-turn conversational reasoning (Greeting / FAQs).
4. Multi-turn ReAct loop execution (Observe -> Reason -> Act -> Observe).
5. Tool execution error recovery & observation feedback.
6. Infinite loop protection & max iteration capping.
7. Resilience against LLM infrastructure failures (Timeout, Service Down, Model Missing).
8. Full end-to-end integration test with real SQLite database session & tool registry.
9. Conditional live Ollama API health & connectivity verification.
"""

from decimal import Decimal
import json
from unittest.mock import MagicMock
import uuid

import pytest

from app.agent.agent import Agent
from app.agent.schemas import AgentAction, AgentResponse
from app.db.database import get_db_context
from app.db.models import Product, StockMovement, Bill
from app.exceptions import (
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from app.ollama_client import OllamaClient as BaseOllamaClient
from app.tools.registry import ToolRegistry, registry as default_registry


# -----------------------------------------------------------------------------
# 1. AgentAction Schema & Safety Validation
# -----------------------------------------------------------------------------

def test_agent_action_validation_rules():
    """Verify AgentAction schema validation rules and strict field constraints."""
    # Tool call requires tool_name
    action_tool = AgentAction(
        action_type="tool_call",
        tool_name="search_products",
        arguments={"query": "atta"},
    )
    assert action_tool.action_type == "tool_call"
    assert action_tool.tool_name == "search_products"
    assert action_tool.arguments == {"query": "atta"}

    # Final response requires content
    action_final = AgentAction(
        action_type="final_response",
        content="Stock for Aashirvaad Atta is 25 kg.",
    )
    assert action_final.action_type == "final_response"
    assert action_final.content == "Stock for Aashirvaad Atta is 25 kg."

    # Clarification requires content
    action_clarify = AgentAction(
        action_type="clarification",
        content="Did you mean 1kg or 5kg Aashirvaad Atta?",
    )
    assert action_clarify.action_type == "clarification"

    # Reject invalid action_type
    with pytest.raises(ValueError):
        AgentAction(action_type="raw_sql_execution")

    # Reject missing tool_name for tool_call
    with pytest.raises(ValueError):
        AgentAction(action_type="tool_call", arguments={"query": "sugar"})

    # Reject missing content for final_response
    with pytest.raises(ValueError):
        AgentAction(action_type="final_response")


# -----------------------------------------------------------------------------
# 2. System Prompt Tool Schema Injection
# -----------------------------------------------------------------------------

def test_agent_system_prompt_tool_injection():
    """Verify system prompt dynamically extracts and formats registered tools."""
    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = [
        {
            "name": "search_products",
            "description": "Search catalog by name or code",
            "input_schema": {
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                }
            },
        }
    ]

    agent = Agent(tool_registry=mock_registry)
    prompt = agent._build_system_prompt()

    assert "AVAILABLE TOOLS:" in prompt
    assert "search_products" in prompt
    assert '"query"' in prompt
    assert "string" in prompt


# -----------------------------------------------------------------------------
# 3. Single-Turn Conversational Reasoning
# -----------------------------------------------------------------------------

def test_agent_single_turn_conversational_response():
    """Verify agent handles conversational greetings in 1 turn without tool calls."""
    mock_llm = MagicMock()
    mock_llm.generate_action.return_value = AgentAction(
        action_type="final_response",
        content="Namaste! How can I assist you with store operations today?",
    )

    agent = Agent(llm_client=mock_llm)
    response = agent.run("Namaste!")

    assert isinstance(response, AgentResponse)
    assert "Namaste!" in response.content
    assert response.metadata["iterations"] == 1
    assert response.metadata["action_type"] == "final_response"


# -----------------------------------------------------------------------------
# 4. Multi-Turn ReAct Loop Execution (Observe -> Reason -> Act)
# -----------------------------------------------------------------------------

def test_agent_multi_turn_react_loop_execution():
    """Verify agent completes a 2-step ReAct loop with tool execution."""
    mock_llm = MagicMock()
    
    # Turn 1: Emit tool call to search stock
    # Turn 2: Receive observation and emit final user answer
    mock_llm.generate_action.side_effect = [
        AgentAction(
            action_type="tool_call",
            tool_name="search_products",
            arguments={"query": "Amul Butter"},
        ),
        AgentAction(
            action_type="final_response",
            content="Amul Butter 500g is currently in stock with 15 units available.",
        ),
    ]

    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = []
    mock_registry.execute.return_value = MagicMock(
        success=True,
        data=[{"name": "Amul Butter 500g", "stock_quantity": 15, "unit_price": "275.00"}],
    )

    agent = Agent(llm_client=mock_llm, tool_registry=mock_registry)
    response = agent.run("Check stock for Amul Butter")

    assert response.content == "Amul Butter 500g is currently in stock with 15 units available."
    assert response.metadata["iterations"] == 2
    mock_registry.execute.assert_called_once_with("search_products", {"query": "Amul Butter"}, context=None)



# -----------------------------------------------------------------------------
# 5. Tool Execution Failure & Observation Feedback
# -----------------------------------------------------------------------------

def test_agent_tool_failure_observation_handling():
    """Verify agent captures tool failures and feeds observation error back to LLM."""
    mock_llm = MagicMock()
    
    # Step 1: Tool call returns invalid arguments or missing product
    # Step 2: Agent synthesizes clarification response
    mock_llm.generate_action.side_effect = [
        AgentAction(
            action_type="tool_call",
            tool_name="get_stock",
            arguments={"product_id": 9999},
        ),
        AgentAction(
            action_type="clarification",
            content="Product ID 9999 was not found in catalog. Could you specify the product name?",
        ),
    ]

    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = []
    mock_registry.execute.return_value = MagicMock(
        success=False,
        error=MagicMock(code="PRODUCT_NOT_FOUND", message="Product ID 9999 does not exist"),
    )

    agent = Agent(llm_client=mock_llm, tool_registry=mock_registry)
    response = agent.run("What is stock for item 9999?")

    assert response.metadata["action_type"] == "clarification"
    assert "9999 was not found" in response.content
    assert response.metadata["iterations"] == 2


# -----------------------------------------------------------------------------
# 6. Infinite Loop Protection & Max Iteration Capping
# -----------------------------------------------------------------------------

def test_agent_max_iteration_capping():
    """Verify agent terminates gracefully when exceeding max_iterations cap."""
    mock_llm = MagicMock()
    # Mock LLM stuck in repetitive tool call loop
    mock_llm.generate_action.return_value = AgentAction(
        action_type="tool_call",
        tool_name="get_low_stock",
        arguments={},
    )

    mock_registry = MagicMock(spec=ToolRegistry)
    mock_registry.list_tools.return_value = []
    mock_registry.execute.return_value = MagicMock(success=True, data=[])

    agent = Agent(llm_client=mock_llm, tool_registry=mock_registry, max_iterations=3)
    response = agent.run("List low stock endlessly")

    assert response.metadata["status"] == "MAX_ITERATIONS_EXCEEDED"
    assert response.metadata["iterations"] == 3
    assert "maximum allowed steps" in response.content


# -----------------------------------------------------------------------------
# 7. LLM Infrastructure Error Resilience
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("exception_cls, error_msg", [
    (OllamaUnavailableError, "Ollama service unavailable at http://localhost:11434"),
    (OllamaTimeoutError, "Ollama request timed out after 30s"),
    (ModelNotFoundError, "Model 'gemma2:2b' not found in Ollama instance"),
])
def test_agent_infrastructure_error_handling(exception_cls, error_msg):
    """Verify agent handles Ollama infrastructure failures gracefully."""
    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = exception_cls(error_msg)

    agent = Agent(llm_client=mock_llm)
    response = agent.run("Show daily report")

    assert "Apologies, an error occurred" in response.content
    assert error_msg in response.metadata["error"]


# -----------------------------------------------------------------------------
# 8. Full End-to-End Real DB + Real Tool Registry Integration Test
# -----------------------------------------------------------------------------

def test_agent_end_to_end_real_db_tool_execution():
    """Verify agent executing tool actions against real SQLite DB and Tool Registry."""
    unique_sku = f"MAGGI-{uuid.uuid4().hex[:8].upper()}"
    
    with get_db_context() as db:
        from app.auth.service import get_or_create_default_store
        get_or_create_default_store(db)

        # Seed test product directly into database with unique SKU
        prod = Product(
            sku=unique_sku,
            name="Agent Eval Maggi 70g",

            brand="Maggi",
            category="Noodles",
            unit="pack",
            pack_size=Decimal("1.00"),
            cost_price=Decimal("12.00"),
            selling_price=Decimal("14.00"),
            mrp=Decimal("14.00"),
            stock_quantity=Decimal("100.00"),
            reorder_level=Decimal("20.00"),
            gst_rate=Decimal("5.00"),
            hsn_code="1902",
            active=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)

        # Create draft bill first to get dynamic bill ID
        res = default_registry.execute("create_draft_bill", {})
        assert res.success
        bill_id = res.data["id"]

        mock_llm = MagicMock()
        
        # Step 1: Agent searches product
        # Step 2: Agent adds item to draft bill
        # Step 3: Agent finalizes bill with CASH
        # Step 4: Agent reports final status
        mock_llm.generate_action.side_effect = [
            AgentAction(
                action_type="tool_call",
                tool_name="search_products",
                arguments={"query": "Maggi 70g"},
            ),
            AgentAction(
                action_type="tool_call",
                tool_name="add_bill_item",
                arguments={"bill_id": bill_id, "product_id": prod.id, "quantity": 10},
            ),
            AgentAction(
                action_type="tool_call",
                tool_name="finalize_bill",
                arguments={"bill_id": bill_id, "payment_method": "CASH"},
            ),
            AgentAction(
                action_type="final_response",
                content=f"Successfully finalized Bill #{bill_id} for 10 units of Maggi 70g via CASH.",
            ),
        ]

        agent = Agent(llm_client=mock_llm, tool_registry=default_registry)
        response = agent.run("Sell 10 packs of Maggi 70g for cash")

        assert response.metadata["iterations"] == 4
        assert f"Successfully finalized Bill #{bill_id}" in response.content

        # Verify real database mutations
        db.refresh(prod)
        assert prod.stock_quantity == Decimal("90.00")  # 100 - 10

        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        assert bill is not None
        assert bill.status == "FINALIZED"
        assert bill.payment_method == "CASH"
        assert bill.taxable_amount == Decimal("140.00")
        assert bill.cgst_amount == Decimal("3.50")
        assert bill.sgst_amount == Decimal("3.50")
        assert bill.tax_total == Decimal("7.00")
        assert bill.grand_total == Decimal("147.00")


# -----------------------------------------------------------------------------
# 9. Live Ollama Connection Check (Optional / Skipped if Offline)
# -----------------------------------------------------------------------------

def test_live_ollama_client_health():
    """Verify live Ollama client health response structure."""
    client = BaseOllamaClient()
    health = client.check_health()
    assert isinstance(health, dict)
    assert "status" in health
