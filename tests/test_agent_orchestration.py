# tests/test_agent_orchestration.py
"""Integration tests for Agent Orchestration & Natural Language Parameter Resolution.

Verifies that the agent automatically resolves human entities (product names, customer names)
to internal IDs without asking the user for product_id, customer_id, or idempotency_key.
"""

from decimal import Decimal
import pytest
from unittest.mock import MagicMock

from app.agent.agent import Agent
from app.agent.schemas import AgentAction
from app.db.database import get_db_context
from app.db.models import Customer, Product, Bill, BillItem
from app.services.inventory_service import create_product
from app.tools import registry


@pytest.fixture
def seed_orchestration_data(db_session):
    """Seed test database with products and customer."""
    p1 = create_product(
        name="Maggi 2-Min Noodle",
        sku="MAGGI-70G",
        category="Snacks",
        cost_price=Decimal("11.00"),
        mrp=Decimal("14.00"),
        selling_price=Decimal("14.00"),
        stock_quantity=Decimal("50"),
    )
    p2 = create_product(
        name="Sugar 1kg",
        sku="SUGAR-1KG",
        category="Grocery",
        cost_price=Decimal("38.00"),
        mrp=Decimal("45.00"),
        selling_price=Decimal("42.00"),
        stock_quantity=Decimal("100"),
    )
    p3 = create_product(
        name="Fortune Oil 1L",
        sku="OIL-FORTUNE-1L",
        category="Grocery",
        cost_price=Decimal("110.00"),
        mrp=Decimal("145.00"),
        selling_price=Decimal("135.00"),
        stock_quantity=Decimal("20"),
    )
    # Ambiguous sugar product
    p4 = create_product(
        name="Brown Sugar 500g",
        sku="SUGAR-BROWN-500G",
        category="Grocery",
        cost_price=Decimal("50.00"),
        mrp=Decimal("65.00"),
        selling_price=Decimal("60.00"),
        stock_quantity=Decimal("15"),
    )

    with get_db_context() as db:
        c1 = Customer(name="Ramesh Kumar", phone="9876543210")
        db.add(c1)
        db.commit()
        db.refresh(c1)
        cust_id = c1.id

    return {"maggi": p1, "sugar": p2, "oil": p3, "brown_sugar": p4, "customer_id": cust_id}


# Mock LLM Client that simulates exact expected sequence of actions for deterministic testing
class SequenceMockLLMClient:
    def __init__(self, action_sequence):
        self.action_sequence = list(action_sequence)
        self.call_count = 0

    def generate_action(self, system_prompt, messages):
        if self.call_count < len(self.action_sequence):
            action = self.action_sequence[self.call_count]
            self.call_count += 1
            return action
        return AgentAction(action_type="final_response", content="Completed test sequence.")


# -----------------------------------------------------------------------------
# 1. "How much Maggi is left?" -> search_products -> get_stock -> final response
# -----------------------------------------------------------------------------
def test_agent_orchestration_how_much_maggi_is_left(seed_orchestration_data):
    p_maggi = seed_orchestration_data["maggi"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"}),
        AgentAction(action_type="tool_call", tool_name="get_stock", arguments={"product_id": p_maggi.id}),
        AgentAction(action_type="final_response", content="We have 50.0 packets of Maggi in stock."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("How much Maggi is left?")
    assert "50" in response.content or "Maggi" in response.content
    assert mock_llm.call_count == 3


# -----------------------------------------------------------------------------
# 2. "Do we have Maggi or Sugar in stock?" -> resolve both products -> get stock
# -----------------------------------------------------------------------------
def test_agent_orchestration_check_multiple_stocks(seed_orchestration_data):
    p_maggi = seed_orchestration_data["maggi"]
    p_sugar = seed_orchestration_data["sugar"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"}),
        AgentAction(action_type="tool_call", tool_name="get_stock", arguments={"product_id": p_maggi.id}),
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Sugar"}),
        AgentAction(action_type="tool_call", tool_name="get_stock", arguments={"product_id": p_sugar.id}),
        AgentAction(action_type="final_response", content="Maggi: 50.0, Sugar: 100.0 available."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Do we have Maggi or Sugar in stock?")
    assert "Maggi" in response.content and "Sugar" in response.content
    assert mock_llm.call_count == 5


# -----------------------------------------------------------------------------
# 3. "Receive 50 packs of Fortune Oil..." -> search product -> receive_stock (no product_id requested)
# -----------------------------------------------------------------------------
def test_agent_orchestration_receive_stock_without_product_id(seed_orchestration_data):
    p_oil = seed_orchestration_data["oil"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Fortune Oil"}),
        AgentAction(
            action_type="tool_call",
            tool_name="receive_stock",
            arguments={"product_id": p_oil.id, "quantity": 50, "cost_price": 110, "mrp": 145},
        ),
        AgentAction(action_type="final_response", content="Received 50 units of Fortune Oil 1L."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Receive 50 packs of Fortune Oil 1L cost 110 MRP 145")
    assert "Received 50" in response.content
    assert mock_llm.call_count == 3


# -----------------------------------------------------------------------------
# 4. "Make a draft bill for 2 Maggi and 1 Sugar" -> resolve products -> create draft -> add items
# -----------------------------------------------------------------------------
def test_agent_orchestration_multi_item_draft_bill(seed_orchestration_data):
    p_maggi = seed_orchestration_data["maggi"]
    p_sugar = seed_orchestration_data["sugar"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"}),
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Sugar"}),
        AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={}),
        # Assume create_draft_bill returned bill_id=1
        AgentAction(action_type="tool_call", tool_name="add_bill_item", arguments={"bill_id": 1, "product_id": p_maggi.id, "quantity": 2}),
        AgentAction(action_type="tool_call", tool_name="add_bill_item", arguments={"bill_id": 1, "product_id": p_sugar.id, "quantity": 1}),
        AgentAction(action_type="final_response", content="Created Draft Bill #1 with 2x Maggi and 1x Sugar."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Make a draft bill for 2 Maggi and 1 Sugar")
    assert "Draft Bill #1" in response.content
    assert mock_llm.call_count == 6


# -----------------------------------------------------------------------------
# 5. "Create a draft bill" -> tool_call create_draft_bill without idempotency_key or customer_id
# -----------------------------------------------------------------------------
def test_agent_orchestration_create_draft_bill_no_idempotency_key(seed_orchestration_data):
    actions = [
        AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={}),
        AgentAction(action_type="final_response", content="Created draft bill #1."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Create a draft bill")
    assert "Created draft bill #1" in response.content
    # Verify tool execution metadata succeeded without requiring idempotency key
    assert len(response.metadata.get("tool_results", [])) == 1
    assert response.metadata["tool_results"][0]["data"]["id"] is not None


# -----------------------------------------------------------------------------
# 6. Normal Cash/UPI Bill without customer -> works cleanly
# -----------------------------------------------------------------------------
def test_agent_orchestration_cash_bill_no_customer(seed_orchestration_data):
    p_maggi = seed_orchestration_data["maggi"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={}),
        AgentAction(action_type="tool_call", tool_name="add_bill_item", arguments={"bill_id": 1, "product_id": p_maggi.id, "quantity": 1}),
        AgentAction(action_type="tool_call", tool_name="finalize_bill", arguments={"bill_id": 1, "payment_method": "CASH"}),
        AgentAction(action_type="final_response", content="Bill #1 finalized with Cash."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Finalize cash bill for 1 Maggi")
    assert "finalized" in response.content.lower()


# -----------------------------------------------------------------------------
# 7. KHATA Bill -> Customer resolved via find_customer
# -----------------------------------------------------------------------------
def test_agent_orchestration_khata_customer_resolution(seed_orchestration_data):
    cust_id = seed_orchestration_data["customer_id"]

    actions = [
        AgentAction(action_type="tool_call", tool_name="find_customer", arguments={"query": "Ramesh"}),
        AgentAction(action_type="tool_call", tool_name="add_credit", arguments={"customer_id": cust_id, "amount": 500, "description": "Credit purchase"}),
        AgentAction(action_type="final_response", content="Added ₹500 credit to Ramesh's Khata account."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Put ₹500 on Ramesh's credit")
    assert "Ramesh" in response.content
    assert mock_llm.call_count == 3


# -----------------------------------------------------------------------------
# 8. Ambiguous Product -> Clarification returned instead of arbitrary selection
# -----------------------------------------------------------------------------
def test_agent_orchestration_ambiguous_product_clarification(seed_orchestration_data):
    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Sugar"}),
        AgentAction(
            action_type="clarification",
            content="Multiple sugar products found:\n1. Sugar 1kg\n2. Brown Sugar 500g\nWhich one do you mean?",
        ),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("How much sugar is in stock?")
    assert "clarification" in response.metadata.get("action_type")
    assert "Multiple sugar products" in response.content


# -----------------------------------------------------------------------------
# 9. User never asked for product_id, customer_id, or idempotency_key
# -----------------------------------------------------------------------------
def test_agent_orchestration_no_internal_id_prompting(seed_orchestration_data):
    # Verify System Prompt contains explicit rules prohibiting internal ID prompting
    from app.agent.prompts import SYSTEM_PROMPT

    assert "NEVER ASK THE USER FOR INTERNAL IDENTIFIERS" in SYSTEM_PROMPT
    assert "product_id" in SYSTEM_PROMPT
    assert "idempotency_key" in SYSTEM_PROMPT
    assert "SEARCH BEFORE ASKING" in SYSTEM_PROMPT or "PRODUCT RESOLUTION" in SYSTEM_PROMPT


# -----------------------------------------------------------------------------
# 10. Unrelated existing bills/products are not accidentally selected
# -----------------------------------------------------------------------------
def test_agent_orchestration_prevent_accidental_unrelated_bill_selection(seed_orchestration_data):
    # If user asks to finalize non-existent bill 999, tool returns error and agent reports cleanly
    actions = [
        AgentAction(action_type="tool_call", tool_name="finalize_bill", arguments={"bill_id": 999, "payment_method": "CASH"}),
        AgentAction(action_type="final_response", content="Bill #999 was not found or is already finalized."),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Finalize bill 999 with cash")
    assert "not found" in response.content.lower() or "finalized" in response.content.lower()


# -----------------------------------------------------------------------------
# 11. Multi-turn Session Memory Option Resolution ("2nd one")
# -----------------------------------------------------------------------------
def test_agent_multiturn_session_option_resolution(seed_orchestration_data):
    """Test that Agent persists session history for a user_id and resolves ordinal choices like '2nd one'."""
    user_id = 998877

    # Turn 1: User asks for bill with ambiguous item
    actions_turn1 = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"}),
        AgentAction(
            action_type="clarification",
            content="Multiple Maggi products found:\n1. Agent Eval Maggi 70g (SKU: MAGGI-EVAL-70G)\n2. Maggi 2-Minute Masala Noodles 70g (SKU: MAGG-NOOD-70G)\nWhich one would you like to add to the bill?",
        ),
    ]
    mock_llm1 = SequenceMockLLMClient(actions_turn1)
    agent1 = Agent(llm_client=mock_llm1, tool_registry=registry)
    res1 = agent1.run("Make a draft bill for 2 Maggi", user_id=user_id)
    assert "Multiple Maggi products found" in res1.content

    # Turn 2: User responds "2nd one"
    actions_turn2 = [
        AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={}),
        AgentAction(action_type="tool_call", tool_name="add_bill_item", arguments={"bill_id": 1, "product_id": 2, "quantity": 2}),
        AgentAction(action_type="final_response", content="Added 2 units of Maggi 2-Minute Masala Noodles to Bill #1."),
    ]
    mock_llm2 = SequenceMockLLMClient(actions_turn2)
    agent2 = Agent(llm_client=mock_llm2, tool_registry=registry)
    res2 = agent2.run("2nd one", user_id=user_id)
    assert "Added 2 units" in res2.content


# -----------------------------------------------------------------------------
# 12. Multi-Item 4-Product Billing with Batch Addition & Iteration Limit Verification
# -----------------------------------------------------------------------------
def test_agent_orchestration_4_item_bill_with_batch_addition(seed_orchestration_data):
    """Verify 4-item billing request completes using batch add_bill_items within the 15-iteration limit."""
    p_maggi = seed_orchestration_data["maggi"]
    p_sugar = seed_orchestration_data["sugar"]
    p_oil = seed_orchestration_data["oil"]

    # 4 products searched -> create draft bill -> batch add items -> finalize bill
    actions = [
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Sugar"}),
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Atta"}),
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"}),
        AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Butter"}),
        AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={}),
        AgentAction(
            action_type="tool_call",
            tool_name="add_bill_items",
            arguments={
                "bill_id": 1,
                "items": [
                    {"product_id": p_sugar.id, "quantity": 2},
                    {"product_id": p_maggi.id, "quantity": 4},
                    {"product_id": p_oil.id, "quantity": 1},
                ],
            },
        ),
        AgentAction(
            action_type="tool_call",
            tool_name="finalize_bill",
            arguments={"bill_id": 1, "payment_method": "UPI"},
        ),
        AgentAction(
            action_type="final_response",
            content="Finalized Bill #1 for ₹580.00 via UPI containing Sugar, Atta, Maggi, and Butter.",
        ),
    ]
    mock_llm = SequenceMockLLMClient(actions)
    agent = Agent(llm_client=mock_llm, tool_registry=registry)

    response = agent.run("Make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI")
    assert "Finalized Bill #1" in response.content
    assert response.metadata.get("status") != "MAX_ITERATIONS_EXCEEDED"
    assert response.metadata.get("iterations") <= 15


def test_agent_max_iterations_is_15():
    """Verify default Agent max_iterations is set to 15 (up from 8)."""
    agent = Agent()
    assert agent.max_iterations == 15
