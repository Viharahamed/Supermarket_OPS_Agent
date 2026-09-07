from decimal import Decimal
from unittest.mock import MagicMock
import pytest

from app.agent.agent import Agent
from app.agent.schemas import AgentAction
from app.auth import ToolExecutionContext, bootstrap_store_and_user
from app.services import inventory_service
from app.db.models import Bill


def test_multi_turn_bill_quantity_update_fresh_context(db_session):
    """Verify update_bill_item succeeds across separate Agent.run turns with fresh contexts."""
    principal = bootstrap_store_and_user(store_name="Multi Turn Store 1", telegram_user_id=99010, db=db_session)
    sid = principal.store_id

    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-MT1-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )

    # Message 1: "Create a draft bill: 2kg sugar"
    ctx1 = ToolExecutionContext(principal=principal, db=db_session)
    run1_step = 0
    def mock_llm_run1(system_prompt, messages):
        nonlocal run1_step
        run1_step += 1
        if run1_step == 1:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "sugar"})
        elif run1_step == 2:
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        elif run1_step == 3:
            bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
            return AgentAction(
                action_type="tool_call",
                tool_name="add_bill_items",
                arguments={
                    "bill_id": bill_rec.id,
                    "items": [{"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"}],
                },
            )
        else:
            return AgentAction(action_type="final_response", content="Draft bill created with 2kg sugar.")

    llm1 = MagicMock()
    llm1.generate_action.side_effect = mock_llm_run1
    agent1 = Agent(llm_client=llm1, max_iterations=8)
    res1 = agent1.run("Create a draft bill: 2kg sugar", context=ctx1)
    assert res1.metadata["action_type"] == "final_response"

    bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
    item_rec = bill_rec.items[0]
    assert item_rec.quantity == Decimal("2.00")

    # Message 2: "Make it 4kg" (Fresh ToolExecutionContext - no search_products executed in Run 2)
    ctx2 = ToolExecutionContext(principal=principal, db=db_session)
    run2_step = 0
    def mock_llm_run2(system_prompt, messages):
        nonlocal run2_step
        run2_step += 1
        if run2_step == 1:
            return AgentAction(
                action_type="tool_call",
                tool_name="update_bill_item",
                arguments={"bill_id": bill_rec.id, "item_id": item_rec.id, "quantity": 4},
            )
        else:
            return AgentAction(action_type="final_response", content="Updated sugar quantity to 4kg.")

    llm2 = MagicMock()
    llm2.generate_action.side_effect = mock_llm_run2
    agent2 = Agent(llm_client=llm2, max_iterations=8)
    res2 = agent2.run("Make it 4kg", context=ctx2)
    assert res2.metadata["action_type"] == "final_response"

    db_session.refresh(item_rec)
    assert item_rec.quantity == Decimal("4.00")


def test_multi_turn_bill_drop_item_and_edit_quantity_fresh_context(db_session):
    """Verify Message 2 ("Drop the sugar, make Maggi 6") edits existing draft without fresh product search."""
    principal = bootstrap_store_and_user(store_name="Multi Turn Store 2", telegram_user_id=99011, db=db_session)
    sid = principal.store_id

    p_sugar = inventory_service.create_product(
        db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-MT2-1KG",
        unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00")
    )
    p_maggi = inventory_service.create_product(
        db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-MT2-70G",
        unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00")
    )

    # Message 1: "Create a draft bill: 2kg sugar, 4 Maggi"
    ctx1 = ToolExecutionContext(principal=principal, db=db_session)
    run1_step = 0
    def mock_llm_run1(system_prompt, messages):
        nonlocal run1_step
        run1_step += 1
        if run1_step == 1:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "sugar"})
        elif run1_step == 2:
            return AgentAction(action_type="tool_call", tool_name="search_products", arguments={"query": "Maggi"})
        elif run1_step == 3:
            return AgentAction(action_type="tool_call", tool_name="create_draft_bill", arguments={})
        elif run1_step == 4:
            bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
            return AgentAction(
                action_type="tool_call",
                tool_name="add_bill_items",
                arguments={
                    "bill_id": bill_rec.id,
                    "items": [
                        {"product_id": p_sugar.id, "quantity": 2, "query_phrase": "sugar"},
                        {"product_id": p_maggi.id, "quantity": 4, "query_phrase": "Maggi"},
                    ],
                },
            )
        else:
            return AgentAction(action_type="final_response", content="Draft bill created with 2kg sugar and 4 Maggi.")

    llm1 = MagicMock()
    llm1.generate_action.side_effect = mock_llm_run1
    agent1 = Agent(llm_client=llm1, max_iterations=8)
    res1 = agent1.run("Create a draft bill: 2kg sugar, 4 Maggi", context=ctx1)
    assert res1.metadata["action_type"] == "final_response"

    bill_rec = db_session.query(Bill).filter(Bill.store_id == sid).first()
    assert len(bill_rec.items) == 2
    items_by_pid = {item.product_id: item for item in bill_rec.items}
    sugar_item = items_by_pid[p_sugar.id]
    maggi_item = items_by_pid[p_maggi.id]

    # Message 2: "Drop the sugar, make Maggi 6" (Fresh ToolExecutionContext - no fresh product search)
    ctx2 = ToolExecutionContext(principal=principal, db=db_session)
    run2_step = 0
    def mock_llm_run2(system_prompt, messages):
        nonlocal run2_step
        run2_step += 1
        if run2_step == 1:
            return AgentAction(
                action_type="tool_call",
                tool_name="remove_bill_item",
                arguments={"bill_id": bill_rec.id, "item_id": sugar_item.id},
            )
        elif run2_step == 2:
            return AgentAction(
                action_type="tool_call",
                tool_name="update_bill_item",
                arguments={"bill_id": bill_rec.id, "item_id": maggi_item.id, "quantity": 6},
            )
        else:
            return AgentAction(action_type="final_response", content="Removed sugar and updated Maggi quantity to 6.")

    llm2 = MagicMock()
    llm2.generate_action.side_effect = mock_llm_run2
    agent2 = Agent(llm_client=llm2, max_iterations=8)
    res2 = agent2.run("Drop the sugar, make Maggi 6", context=ctx2)
    assert res2.metadata["action_type"] == "final_response"

    db_session.refresh(bill_rec)
    assert len(bill_rec.items) == 1
    assert bill_rec.items[0].product_id == p_maggi.id
    assert bill_rec.items[0].quantity == Decimal("6.00")
