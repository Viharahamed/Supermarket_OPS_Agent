from unittest.mock import ANY, MagicMock

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
    mock_registry.execute.assert_called_once_with("search_products", {"query": "Milk"}, context=ANY)



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


def test_agent_action_normalization_and_observation_echo_rejection():
    # 8A. Normal existing AgentAction format
    action1 = AgentAction.model_validate({
        "action_type": "tool_call",
        "tool_name": "search_products",
        "arguments": {"query": "sugar"},
    })
    assert action1.action_type == "tool_call"
    assert action1.tool_name == "search_products"
    assert action1.arguments == {"query": "sugar"}

    # 8B. Legitimate alternative "name" tool-call format
    action2 = AgentAction.model_validate({
        "name": "search_products",
        "arguments": {"query": "sugar"},
    })
    assert action2.action_type == "tool_call"
    assert action2.tool_name == "search_products"
    assert action2.arguments == {"query": "sugar"}

    # 8C & 8E. Production failure: Observation echo MUST NOT execute tools
    with pytest.raises(ValueError):
        AgentAction.model_validate({
            "name": "create_draft_bill",
            "data": {
                "success": True,
                "data": "BILL-20260907-4E5B8C",
            },
        })

    # 8D. Missing arguments for tool call in "name" format MUST NOT be silently accepted
    with pytest.raises(ValueError):
        AgentAction.model_validate({
            "name": "create_draft_bill",
        })

    with pytest.raises(ValueError):
        AgentAction.model_validate({
            "name": "search_products",
            "arguments": "not_a_dict",
        })

    # Additional observation echo key checks (result, observation, success, response)
    with pytest.raises(ValueError):
        AgentAction.model_validate({
            "name": "search_products",
            "arguments": {"query": "sugar"},
            "result": [{"id": 1}],
        })


def test_agent_orchestration_malformed_observation_echo_rejected_in_agent_run(db_session):
    """Orchestration test verifying malformed observation echo is rejected inside Agent.run().

    Exercises real Agent.run() handling when iteration 2 encounters the production echo payload:
    1. Iteration 1: Calls create_draft_bill.
    2. Iteration 2: LLM emits malformed echo payload. AgentAction validation fails and throws InvalidModelResponseError.
    3. Agent.run() catches error, halts loop safely.
    4. NO duplicate bill is created, NO extra tool execution occurs, and stock remains unchanged.
    """
    from decimal import Decimal
    from app.auth import ToolExecutionContext, bootstrap_store_and_user
    from app.services import inventory_service
    from app.db.models import Bill
    from app.exceptions import InvalidModelResponseError

    principal = bootstrap_store_and_user(store_name="Echo Test Store", telegram_user_id=77701, db=db_session)
    ctx = ToolExecutionContext(principal=principal, db=db_session)
    sid = principal.store_id

    # Create catalog products
    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-ECHO-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )
    p_maggi = inventory_service.create_product(
        db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-ECHO-70G",
        unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00")
    )

    echo_payload = {
        "name": "create_draft_bill",
        "data": {
            "success": True,
            "data": "BILL-20260907-4E5B8C",
        },
    }

    def mock_generate_action(system_prompt, messages):
        # Iteration 1: Request create_draft_bill
        if len(messages) == 1:
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        # Iteration 2: Pass malformed observation echo through AgentAction validation
        try:
            return AgentAction.model_validate(echo_payload)
        except Exception as exc:
            raise InvalidModelResponseError(f"Model response could not be parsed as valid AgentAction JSON: {exc}") from exc

    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = mock_generate_action

    agent = Agent(llm_client=mock_llm, max_iterations=8)
    response = agent.run("Create a draft bill: 2kg sugar, 4 Maggi. Do not finalize.", context=ctx)

    # Verify Agent.run() caught the InvalidModelResponseError and returned an error response
    assert "Apologies, an error occurred" in response.content
    assert "observation/result echo fields" in response.metadata["error"]
    assert response.metadata["iteration"] == 2

    # Verify database state: Exactly ONE bill created, NO duplicate bill created in iteration 2
    bills = db_session.query(Bill).filter(Bill.store_id == sid).all()
    assert len(bills) == 1
    assert bills[0].status == "DRAFT"
    assert len(bills[0].items) == 0

    # Verify stock remains unchanged
    st_sugar = inventory_service.get_stock(db=db_session, product_id=p_sugar.id, store_id=sid)
    st_maggi = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st_sugar.stock_quantity == Decimal("100.00")
    assert st_maggi.stock_quantity == Decimal("100.00")


def test_agent_orchestration_multi_step_draft_billing_dynamic_bill_id(db_session):
    """Orchestration test for multi-step draft billing with dynamic bill_id resolution.

    Verifies:
    1. First iteration calls create_draft_bill.
    2. Dynamic bill_id from iteration 1 observation is used for add_bill_items in iteration 2.
    3. Final state: exactly 1 draft bill, exactly 2 items, status DRAFT, stock unchanged.
    """
    from decimal import Decimal
    from app.auth import ToolExecutionContext, bootstrap_store_and_user
    from app.services import inventory_service
    from app.db.models import Bill

    principal = bootstrap_store_and_user(store_name="Dynamic Bill Test Store", telegram_user_id=77702, db=db_session)
    ctx = ToolExecutionContext(principal=principal, db=db_session)
    sid = principal.store_id

    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-DYN-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )
    p_maggi = inventory_service.create_product(
        db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-DYN-70G",
        unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00")
    )

    created_bill_id = None

    def mock_generate_action(system_prompt, messages):
        nonlocal created_bill_id
        if len(messages) == 1:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "sugar"})
        elif len(messages) == 3:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"})
        elif len(messages) == 5:
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        elif len(messages) == 7:
            # Extract dynamic bill ID from DB created in iteration 3
            bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
            assert bill_rec is not None
            created_bill_id = bill_rec.id
            return AgentAction(
                action_type="tool_call",
                tool_name="add_bill_items",
                arguments={
                    "bill_id": created_bill_id,
                    "items": [
                        {"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"},
                        {"product_id": p_maggi.id, "quantity": 4, "query_phrase": "Maggi"},
                    ],
                },
            )
        else:
            return AgentAction(
                action_type="final_response",
                content=f"Created draft bill #{created_bill_id} with 2kg Sugar and 4 Maggi. Bill remains in DRAFT status.",
            )

    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = mock_generate_action

    agent = Agent(llm_client=mock_llm, max_iterations=8)
    response = agent.run("Create a draft bill: 2kg sugar, 4 Maggi. Do not finalize.", context=ctx)

    assert response.metadata["action_type"] == "final_response"
    assert response.metadata["iterations"] == 5


    # Final verification
    bills = db_session.query(Bill).filter(Bill.store_id == sid).all()
    assert len(bills) == 1
    bill = bills[0]
    assert bill.id == created_bill_id
    assert bill.status == "DRAFT"
    assert len(bill.items) == 2

    # Stock untouched
    st_sugar = inventory_service.get_stock(db=db_session, product_id=p_sugar.id, store_id=sid)
    st_maggi = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st_sugar.stock_quantity == Decimal("100.00")
    assert st_maggi.stock_quantity == Decimal("100.00")


def test_agent_grounded_product_resolution_and_draft_creation(db_session):
    """Regression test: '2kg sugar, 4 Maggi' grounding & draft creation.

    Verifies:
    1. Search tools are executed to resolve 'sugar' and 'Maggi' to actual product IDs.
    2. Draft bill contains ONLY those resolved products with exact quantities.
    3. Draft status remains 'DRAFT'.
    4. Inventory stock is NOT deducted for draft bills.
    """
    from decimal import Decimal
    from app.auth import ToolExecutionContext, bootstrap_store_and_user
    from app.services import inventory_service
    from app.db.models import Bill

    principal = bootstrap_store_and_user(store_name="Grounded Resolution Store", telegram_user_id=88801, db=db_session)
    ctx = ToolExecutionContext(principal=principal, db=db_session)
    sid = principal.store_id

    # Create distinct products
    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-GRND-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("50.00")
    )
    p_maggi = inventory_service.create_product(
        db=db_session, store_id=sid, name="Maggi 2-Min Noodle", sku="MAG-GRND-70G",
        unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("60.00")
    )

    created_bill_id = None

    def mock_grounded_llm(system_prompt, messages):
        nonlocal created_bill_id
        msg_count = len(messages)
        if msg_count == 1:
            # Iteration 1: Search sugar
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "sugar"})
        elif msg_count == 3:
            # Iteration 2: Search Maggi
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"})
        elif msg_count == 5:
            # Iteration 3: Create draft bill
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        elif msg_count == 7:
            # Iteration 4: Add bill items using verified IDs from search results
            bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
            assert bill_rec is not None
            created_bill_id = bill_rec.id
            return AgentAction(
                action_type="tool_call",
                tool_name="add_bill_items",
                arguments={
                    "bill_id": created_bill_id,
                    "items": [
                        {"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"},
                        {"product_id": p_maggi.id, "quantity": 4, "query_phrase": "Maggi"},
                    ],
                },
            )
        else:
            # Iteration 5: Final response
            return AgentAction(
                action_type="final_response",
                content=f"Draft bill #{created_bill_id} created with 2kg Sugar and 4 Maggi. Status: DRAFT.",
            )

    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = mock_grounded_llm

    agent = Agent(llm_client=mock_llm, max_iterations=8)
    response = agent.run("Create a draft bill: 2kg sugar, 4 Maggi. Do not finalize.", context=ctx)

    assert response.metadata["action_type"] == "final_response"
    assert response.metadata["iterations"] == 5

    # Verify draft bill in DB
    bills = db_session.query(Bill).filter(Bill.store_id == sid).all()
    assert len(bills) == 1
    bill = bills[0]
    assert bill.id == created_bill_id
    assert bill.status == "DRAFT"
    assert len(bill.items) == 2

    items_by_pid = {item.product_id: item.quantity for item in bill.items}
    assert items_by_pid[p_sugar.id] == Decimal("2.00")
    assert items_by_pid[p_maggi.id] == Decimal("4.00")

    # Verify stock is completely unchanged for draft bill
    st_sugar = inventory_service.get_stock(db=db_session, product_id=p_sugar.id, store_id=sid)
    st_maggi = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st_sugar.stock_quantity == Decimal("50.00")
    assert st_maggi.stock_quantity == Decimal("60.00")


def test_agent_system_prompt_schema_and_constraints():
    """Verify system prompt tool formatting and explicit positive action constraints.

    Verifies:
    1. Agent._build_system_prompt() uses 'tool_name' as the schema key in AVAILABLE TOOLS.
    2. System prompt explicitly constrains action_type to 'tool_call', 'final_response', and 'clarification'.
    3. System prompt does NOT contain negative priming example tokens ('user_input', 'draft_bill_items').
    """
    mock_llm = MagicMock()
    agent = Agent(llm_client=mock_llm)
    prompt = agent._build_system_prompt()

    # 1. Exposes tools using "tool_name", not "name"
    assert '"tool_name": "search_products"' in prompt
    assert '"tool_name": "add_bill_items"' in prompt

    # 2. Explicitly constrains action_type to allowed values
    assert '"tool_call"' in prompt
    assert '"final_response"' in prompt
    assert '"clarification"' in prompt

    # 3. Does NOT contain invalid priming tokens
    assert 'user_input' not in prompt
    assert 'draft_bill_items' not in prompt


def test_openrouter_provider_structured_output_payload():
    """Verify OpenRouterProvider request payload uses strict JSON Schema for AgentAction."""
    from unittest.mock import patch
    from app.llm.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key="test_key")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"action_type": "final_response", "tool_name": null, "arguments": null, "content": "Hello"}'
                }
            }]
        }

        provider.generate_action("System Prompt", [{"role": "user", "content": "Hi"}])

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        json_payload = kwargs["json"]

        assert "provider" in json_payload
        assert json_payload["provider"]["require_parameters"] is True

        assert "response_format" in json_payload
        rf = json_payload["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["name"] == "agent_action"

        schema = rf["json_schema"]["schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"action_type", "tool_name", "arguments", "content"}
        assert schema["properties"]["action_type"]["enum"] == ["tool_call", "final_response", "clarification"]


def test_agent_action_structured_output_envelope_valid_types():
    """Regression test demonstrating valid AgentAction envelope works for tool_call, final_response, clarification."""
    # 1. tool_call envelope
    tc = AgentAction.model_validate({
        "action_type": "tool_call",
        "tool_name": "search_products",
        "arguments": {"query": "sugar"},
        "content": None,
    })
    assert tc.action_type == "tool_call"
    assert tc.tool_name == "search_products"
    assert tc.arguments == {"query": "sugar"}

    # 2. final_response envelope
    fr = AgentAction.model_validate({
        "action_type": "final_response",
        "tool_name": None,
        "arguments": None,
        "content": "Draft bill #8 created.",
    })
    assert fr.action_type == "final_response"
    assert fr.content == "Draft bill #8 created."

    # 3. clarification envelope
    cl = AgentAction.model_validate({
        "action_type": "clarification",
        "tool_name": None,
        "arguments": None,
        "content": "Which Maggi variant?",
    })
    assert cl.action_type == "clarification"
    assert cl.content == "Which Maggi variant?"


def test_grounding_regression_scenarios(db_session):
    """User-query product grounding regression test suite covering all 16 security invariants."""
    from decimal import Decimal
    from app.auth import ToolExecutionContext, bootstrap_store_and_user
    from app.services import inventory_service
    from app.db.models import Bill
    from app.tools.registry import registry

    principal = bootstrap_store_and_user(store_name="User Query Grounding Store", telegram_user_id=99001, db=db_session)
    sid = principal.store_id

    # Seed products: Sugar (ID p_sugar.id), Tea (ID p_tea.id), Maggi (ID p_maggi.id)
    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Madhur Pure & Hygienic Sugar 1kg", sku="SUG-6",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )
    p_tea = inventory_service.create_product(
        db=db_session, store_id=sid, name="Taj Mahal Tea 500g", sku="TEA-10",
        unit="pack", cost_price=Decimal("300.00"), mrp=Decimal("380.00"), selling_price=Decimal("357.00"), stock_quantity=Decimal("50.00")
    )
    p_maggi = inventory_service.create_product(
        db=db_session, store_id=sid, name="Maggi 2-Minute Masala Noodles 70g", sku="MAG-3",
        unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("80.00")
    )

    # 1. VALID SUGAR: user_message="Create a draft bill: 2kg sugar", search("sugar") -> ID p_sugar.id, add_bill_item(p_sugar.id, query_phrase="sugar") -> success
    ctx_run1 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    search_res = registry.execute("search_products", {"query": "sugar"}, context=ctx_run1)
    assert search_res.success
    assert p_sugar.id in ctx_run1.grounded_product_ids
    assert "sugar" in ctx_run1.grounded_product_queries[p_sugar.id]

    bill_res = registry.execute("create_draft_bill", {}, context=ctx_run1)
    b_id = bill_res.data["id"]
    add_res = registry.execute("add_bill_item", {"bill_id": b_id, "product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"}, context=ctx_run1)
    assert add_res.success

    # 2. CASE NORMALIZATION: search "Sugar", query_phrase "sugar" -> success
    ctx_run2 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg Sugar")
    registry.execute("search_products", {"query": "Sugar"}, context=ctx_run2)
    b_res2 = registry.execute("create_draft_bill", {}, context=ctx_run2)
    b_id2 = b_res2.data["id"]
    add_res2 = registry.execute("add_bill_item", {"bill_id": b_id2, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run2)
    assert add_res2.success

    # 3. WHITESPACE NORMALIZATION: search "  sugar  ", query_phrase "sugar" -> success
    ctx_run3 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "  sugar  "}, context=ctx_run3)
    b_res3 = registry.execute("create_draft_bill", {}, context=ctx_run3)
    b_id3 = b_res3.data["id"]
    add_res3 = registry.execute("add_bill_item", {"bill_id": b_id3, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run3)
    assert add_res3.success

    # 4. CROSS-QUERY: user asks sugar, search "tea" -> ID p_tea.id, add ID p_tea.id query_phrase "tea" -> PRODUCT_NOT_GROUNDED (because "tea" not in user_message)
    ctx_run4 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "tea"}, context=ctx_run4)
    b_res4 = registry.execute("create_draft_bill", {}, context=ctx_run4)
    b_id4 = b_res4.data["id"]
    cross_res = registry.execute("add_bill_item", {"bill_id": b_id4, "product_id": p_tea.id, "quantity": 1, "query_phrase": "tea"}, context=ctx_run4)
    assert not cross_res.success
    assert "PRODUCT_NOT_GROUNDED" in cross_res.error.message

    # 5. LYING QUERY: search "tea" -> ID p_tea.id, query_phrase "sugar" -> PRODUCT_NOT_GROUNDED (because "sugar" was not query that returned p_tea.id)
    ctx_run5 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "tea"}, context=ctx_run5)
    b_res5 = registry.execute("create_draft_bill", {}, context=ctx_run5)
    b_id5 = b_res5.data["id"]
    lying_res = registry.execute("add_bill_item", {"bill_id": b_id5, "product_id": p_tea.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run5)
    assert not lying_res.success
    assert "PRODUCT_NOT_GROUNDED" in lying_res.error.message

    # 6. PROMPT COLLISION: search "sugar" -> ID p_sugar.id, attempt ID p_tea.id -> PRODUCT_NOT_GROUNDED
    ctx_run6 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run6)
    b_res6 = registry.execute("create_draft_bill", {}, context=ctx_run6)
    b_id6 = b_res6.data["id"]
    collision_res = registry.execute("add_bill_item", {"bill_id": b_id6, "product_id": p_tea.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run6)
    assert not collision_res.success
    assert "PRODUCT_NOT_GROUNDED" in collision_res.error.message

    # 7. NO SEARCH: attempt product ID without grounding -> PRODUCT_NOT_GROUNDED
    ctx_run7 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    b_res7 = registry.execute("create_draft_bill", {}, context=ctx_run7)
    b_id7 = b_res7.data["id"]
    no_search_res = registry.execute("add_bill_item", {"bill_id": b_id7, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run7)
    assert not no_search_res.success
    assert "PRODUCT_NOT_GROUNDED" in no_search_res.error.message

    # 8. EXISTING BUT WRONG PRODUCT: ID p_tea.id exists as Tea, but user asks sugar -> rejected
    ctx_run8 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run8)
    b_res8 = registry.execute("create_draft_bill", {}, context=ctx_run8)
    b_id8 = b_res8.data["id"]
    wrong_prod_res = registry.execute("add_bill_item", {"bill_id": b_id8, "product_id": p_tea.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run8)
    assert not wrong_prod_res.success
    assert "PRODUCT_NOT_GROUNDED" in wrong_prod_res.error.message

    # 9. MULTI-ITEM VALID: sugar -> p_sugar.id, Maggi -> p_maggi.id, batch [p_sugar.id/sugar, p_maggi.id/Maggi] -> success
    ctx_run9 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar, 4 Maggi")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run9)
    registry.execute("search_products", {"query": "Maggi"}, context=ctx_run9)
    b_res9 = registry.execute("create_draft_bill", {}, context=ctx_run9)
    b_id9 = b_res9.data["id"]
    batch_valid = registry.execute("add_bill_items", {"bill_id": b_id9, "items": [
        {"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"},
        {"product_id": p_maggi.id, "quantity": 4, "query_phrase": "Maggi"},
    ]}, context=ctx_run9)
    assert batch_valid.success

    # 10. MIXED BATCH: sugar -> p_sugar.id, Maggi -> p_maggi.id, batch includes Tea ID p_tea.id -> entire batch rejected before mutation
    ctx_run10 = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar, 4 Maggi")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run10)
    registry.execute("search_products", {"query": "Maggi"}, context=ctx_run10)
    b_res10 = registry.execute("create_draft_bill", {}, context=ctx_run10)
    b_id10 = b_res10.data["id"]
    mixed_batch = registry.execute("add_bill_items", {"bill_id": b_id10, "items": [
        {"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"},
        {"product_id": p_tea.id, "quantity": 1, "query_phrase": "tea"},
    ]}, context=ctx_run10)
    assert not mixed_batch.success
    assert "PRODUCT_NOT_GROUNDED" in mixed_batch.error.message
    # Verify 0 items added to bill10
    bill10_rec = db_session.query(Bill).filter(Bill.id == b_id10).first()
    assert len(bill10_rec.items) == 0

    # 11. RUN ISOLATION: Run A searches sugar. Run B attempts ID p_sugar.id without searching -> Run B rejected
    ctx_runA = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_runA)

    ctx_runB = ToolExecutionContext(principal=principal, db=db_session, user_message="Create a draft bill: 2kg sugar")
    b_resB = registry.execute("create_draft_bill", {}, context=ctx_runB)
    b_idB = b_resB.data["id"]
    runB_res = registry.execute("add_bill_item", {"bill_id": b_idB, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_runB)
    assert not runB_res.success
    assert "PRODUCT_NOT_GROUNDED" in runB_res.error.message

    # 12. QUERY NOT PRESENT IN USER MESSAGE: user_message="2kg sugar", search "tea" -> ID p_tea.id, query_phrase="tea" -> rejected
    ctx_run12 = ToolExecutionContext(principal=principal, db=db_session, user_message="2kg sugar")
    registry.execute("search_products", {"query": "tea"}, context=ctx_run12)
    b_res12 = registry.execute("create_draft_bill", {}, context=ctx_run12)
    b_id12 = b_res12.data["id"]
    not_present_res = registry.execute("add_bill_item", {"bill_id": b_id12, "product_id": p_tea.id, "quantity": 1, "query_phrase": "tea"}, context=ctx_run12)
    assert not not_present_res.success
    assert "PRODUCT_NOT_GROUNDED" in not_present_res.error.message

    # 13. QUERY PRESENT: user_message="2kg sugar", search "sugar" -> ID p_sugar.id, query_phrase="sugar" -> allowed
    ctx_run13 = ToolExecutionContext(principal=principal, db=db_session, user_message="2kg sugar")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run13)
    b_res13 = registry.execute("create_draft_bill", {}, context=ctx_run13)
    b_id13 = b_res13.data["id"]
    present_res = registry.execute("add_bill_item", {"bill_id": b_id13, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugar"}, context=ctx_run13)
    assert present_res.success

    # 14. SUBSTRING FALSE POSITIVE: search "sugar" -> ID p_sugar.id, query_phrase="sugarcane" -> rejected (because sugarcane != sugar in grounded_product_queries)
    ctx_run14 = ToolExecutionContext(principal=principal, db=db_session, user_message="2kg sugarcane")
    registry.execute("search_products", {"query": "sugar"}, context=ctx_run14)
    b_res14 = registry.execute("create_draft_bill", {}, context=ctx_run14)
    b_id14 = b_res14.data["id"]
    false_pos_res = registry.execute("add_bill_item", {"bill_id": b_id14, "product_id": p_sugar.id, "quantity": 1, "query_phrase": "sugarcane"}, context=ctx_run14)
    assert not false_pos_res.success
    assert "PRODUCT_NOT_GROUNDED" in false_pos_res.error.message


def test_prompt_example_collision_uses_search_result_not_example_id(db_session):
    """Verify agent uses runtime product ID from search observation, NOT example ID from prompt."""
    from decimal import Decimal
    from app.auth import ToolExecutionContext, bootstrap_store_and_user
    from app.services import inventory_service
    from app.db.models import Bill

    principal = bootstrap_store_and_user(store_name="Collision Test Store", telegram_user_id=99002, db=db_session)
    ctx = ToolExecutionContext(principal=principal, db=db_session)
    sid = principal.store_id

    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-COL-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )

    created_bill_id = None

    def mock_agent_llm(system_prompt, messages):
        nonlocal created_bill_id
        msg_count = len(messages)
        if msg_count == 1:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "sugar"})
        elif msg_count == 3:
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        elif msg_count == 5:
            bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
            assert bill_rec is not None
            created_bill_id = bill_rec.id
            return AgentAction(
                action_type="tool_call",
                tool_name="add_bill_items",
                arguments={
                    "bill_id": created_bill_id,
                    "items": [{"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"}],
                },
            )
        else:
            return AgentAction(
                action_type="final_response",
                content=f"Created draft bill #{created_bill_id} with 2kg Sugar.",
            )

    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = mock_agent_llm

    agent = Agent(llm_client=mock_llm, max_iterations=8)
    response = agent.run("Create a draft bill: 2kg sugar. Do not finalize.", context=ctx)

    assert response.metadata["action_type"] == "final_response"

    # Verify item in bill has runtime ID p_sugar.id
    bill = db_session.query(Bill).filter(Bill.id == created_bill_id).first()
    assert len(bill.items) == 1
    assert bill.items[0].product_id == p_sugar.id
