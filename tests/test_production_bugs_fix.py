# tests/test_production_bugs_fix.py
"""Comprehensive regression test suite for production hardening fixes:
1. Dynamic runtime date context & date default handling
2. Tool registry registration of get_daily_close & optional date default
3. Khata customer lookup normalization, ambiguity handling, & strict tenant isolation
4. Close-day filtering (excluding DRAFT/CANCELLED bills, no double counting)
5. Agent end-to-end orchestration for "Close the day"
"""

import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from app.db.database import get_db_context, init_db
from app.db.models import Customer, Bill, BillItem, Product, Store
from app.services.reporting_service import get_store_date, get_daily_sales, daily_close
from app.services.billing_service import create_draft_bill, add_bill_item, finalize_bill
from app.tools.registry import registry
from app.tools.schemas import GetDailyCloseInput, GetDailySalesInput, FindCustomerInput
from app.tools.reporting import get_daily_close, get_daily_sales
from app.tools.khata import find_customer, create_customer
from app.agent.agent import Agent, AgentAction, AgentResponse, ToolExecutionContext, AuthenticatedPrincipal


def _create_test_store(db, store_id=1, name="Test Store"):
    store = db.query(Store).filter_by(id=store_id).first()
    if not store:
        store = Store(id=store_id, name=name, address="Test Address", gstin="29ABCDE1234F1Z5")
        db.add(store)
        db.commit()
        db.refresh(store)
    return store


def _create_test_product(db, store_id=1):
    import uuid
    _create_test_store(db, store_id)
    product = Product(
        store_id=store_id,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Test Product",
        cost_price=Decimal("10.00"),
        selling_price=Decimal("15.00"),
        mrp=Decimal("20.00"),
        gst_rate=Decimal("5.00"),
        stock_quantity=Decimal("100.00"),
        active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# ===========================================================================
# 1. DATE TESTS (1 - 6)
# ===========================================================================

def test_1_get_store_date_uses_configured_timezone():
    """Verify get_store_date returns correct local date in IST."""
    d = get_store_date()
    expected_d = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    assert d == expected_d


def test_2_agent_system_prompt_contains_dynamic_store_date():
    """Verify Agent system prompt dynamically embeds CURRENT STORE DATE."""
    agent = Agent()
    prompt = agent._build_system_prompt()
    today_str = get_store_date().isoformat()
    assert f"CURRENT STORE DATE: {today_str}" in prompt


def test_3_todays_sales_without_explicit_date_uses_current_store_date():
    """Verify get_daily_sales defaults to today when report_date is None."""
    inp = GetDailySalesInput(report_date=None)
    result = get_daily_sales(inp)
    today_str = get_store_date().isoformat()
    assert result["period"]["start"] == today_str


def test_4_hallucinated_stale_date_fallback_prevention():
    """Verify GetDailySalesInput fallback logic prioritizes explicit input or defaults to get_store_date when omitted."""
    # When report_date is omitted:
    inp = GetDailySalesInput()
    res = get_daily_sales(inp)
    assert res["period"]["start"] == get_store_date().isoformat()


def test_5_explicit_historical_date_works():
    """Verify historical date is preserved when explicitly requested."""
    inp = GetDailySalesInput(report_date="2026-01-15")
    res = get_daily_sales(inp)
    assert res["period"]["start"] == "2026-01-15"


def test_6_what_date_is_it_today_uses_runtime_date():
    """Verify LLM agent prompt provides runtime store date context."""
    agent = Agent()
    prompt = agent._build_system_prompt()
    current_date = get_store_date().isoformat()
    assert current_date in prompt


# ===========================================================================
# 2. DAILY CLOSE TESTS (7 - 14)
# ===========================================================================

def test_7_get_daily_close_is_registered_in_registry():
    """Verify get_daily_close tool is registered in ToolRegistry."""
    tool_def = registry.get("get_daily_close")
    assert tool_def is not None
    assert tool_def.name == "get_daily_close"


def test_8_get_daily_close_executes_through_registry():
    """Verify executing get_daily_close through registry.execute succeeds."""
    init_db()
    with get_db_context() as db:
        _create_test_store(db, store_id=1)
    
    ctx = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=1, store_id=1, role="OWNER"))
    res = registry.execute("get_daily_close", {}, context=ctx)
    assert res.success is True
    assert "daily_sales" in res.data
    assert "payment_breakdown" in res.data


def test_9_report_date_can_be_omitted_in_get_daily_close_input():
    """Verify GetDailyCloseInput allows report_date=None."""
    inp = GetDailyCloseInput()
    assert inp.report_date is None


def test_10_omitted_report_date_defaults_to_get_store_date():
    """Verify get_daily_close handler uses get_store_date when report_date is omitted."""
    res = get_daily_close(GetDailyCloseInput())
    today_str = get_store_date().isoformat()
    assert res["period"]["start"] == today_str


def test_11_explicit_historical_report_date_works():
    """Verify get_daily_close uses explicit report_date when provided."""
    res = get_daily_close(GetDailyCloseInput(report_date="2026-05-20"))
    assert res["period"]["start"] == "2026-05-20"


def test_12_13_14_close_day_excludes_drafts_cancelled_and_no_double_counting():
    """Verify daily close includes ONLY finalized bills for the target store and date."""
    init_db()
    test_sid = 999
    with get_db_context() as db:
        store = _create_test_store(db, store_id=test_sid)
        product = _create_test_product(db, store_id=test_sid)

        # 1. Finalized bill today
        draft1 = create_draft_bill(db, store_id=test_sid)
        add_bill_item(db, draft1.id, product.id, quantity=2, store_id=test_sid)
        fin1 = finalize_bill(db, draft1.id, payment_method="CASH", store_id=test_sid)

        # 2. Draft bill today (unfinalized)
        draft2 = create_draft_bill(db, store_id=test_sid)
        add_bill_item(db, draft2.id, product.id, quantity=5, store_id=test_sid)

        # 3. Cancelled bill today
        draft3 = create_draft_bill(db, store_id=test_sid)
        draft3.status = "CANCELLED"
        db.commit()

        # Run daily close report
        close_report = daily_close(get_store_date(), store_id=test_sid)

        # Total finalized bills should be 1 (draft1), not draft2 or draft3
        assert close_report.daily_sales.bill_count == 1
        assert close_report.daily_sales.grand_total == fin1.grand_total


# ===========================================================================
# 3. KHATA CUSTOMER LOOKUP TESTS (15 - 22)
# ===========================================================================

def test_15_16_17_18_khata_customer_lookup_normalization():
    """Verify find_customer normalizes whitespace, case, possessives ('s), and punctuation."""
    init_db()
    test_sid = 888
    with get_db_context() as db:
        _create_test_store(db, store_id=test_sid)
        c = Customer(store_id=test_sid, name="Ramesh Kumar", phone="9876543210")
        db.add(c)
        db.commit()

    ctx = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=1, store_id=test_sid, role="OWNER"))

    # Exact name
    res1 = find_customer(FindCustomerInput(query="Ramesh Kumar"), context=ctx)
    assert res1["count"] == 1
    assert res1["customers"][0]["name"] == "Ramesh Kumar"

    # Whitespace padded
    res2 = find_customer(FindCustomerInput(query="  Ramesh Kumar  "), context=ctx)
    assert res2["count"] == 1

    # Case-insensitive
    res3 = find_customer(FindCustomerInput(query="ramesh kumar"), context=ctx)
    assert res3["count"] == 1

    # Possessive 's suffix & trailing noise
    res4 = find_customer(FindCustomerInput(query="Ramesh Kumar's credit"), context=ctx)
    assert res4["count"] == 1
    assert res4["customers"][0]["name"] == "Ramesh Kumar"


def test_19_multiple_matching_customers_produce_ambiguity():
    """Verify multiple matching customers return count > 1 (ambiguity)."""
    init_db()
    test_sid = 777
    with get_db_context() as db:
        _create_test_store(db, store_id=test_sid)
        db.add(Customer(store_id=test_sid, name="Ramesh Kumar", phone="9876543210"))
        db.add(Customer(store_id=test_sid, name="Ramesh Patel", phone="9876543219"))
        db.commit()

    ctx = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=1, store_id=test_sid, role="OWNER"))
    res = find_customer(FindCustomerInput(query="Ramesh"), context=ctx)
    assert res["count"] == 2
    assert len(res["customers"]) == 2


def test_20_21_22_wrong_store_customer_isolation_and_missing_customer():
    """Verify strict tenant isolation in find_customer."""
    init_db()
    with get_db_context() as db:
        _create_test_store(db, store_id=1)
        _create_test_store(db, store_id=2, name="Store 2")
        db.add(Customer(store_id=2, name="Secret Customer", phone="9111111111"))
        db.commit()

    # Query from Store 1 context
    ctx1 = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=1, store_id=1, role="OWNER"))
    res = find_customer(FindCustomerInput(query="Secret Customer"), context=ctx1)
    assert res["count"] == 0
    assert len(res["customers"]) == 0

    # Query from Store 2 context
    ctx2 = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=2, store_id=2, role="OWNER"))
    res2 = find_customer(FindCustomerInput(query="Secret Customer"), context=ctx2)
    assert res2["count"] == 1


# ===========================================================================
# 4. AGENT INTEGRATION TEST (23)
# ===========================================================================

def test_23_close_the_day_agent_orchestration():
    """Verify agent generates get_daily_close tool call for 'Close the day'."""
    mock_llm = MagicMock()
    mock_llm.generate_action.side_effect = [
        AgentAction(action_type="tool_call", tool_name="get_daily_close", arguments={}),
        AgentAction(action_type="final_response", content="Day closed successfully."),
    ]
    agent = Agent(llm_client=mock_llm)
    ctx = ToolExecutionContext(principal=AuthenticatedPrincipal(user_id=1, store_id=1, role="OWNER"))
    response = agent.run("Close the day", context=ctx)

    assert mock_llm.generate_action.call_count == 2
    assert response.content == "Day closed successfully."
    assert any(tr.get("tool_name") == "get_daily_close" for tr in response.metadata.get("tool_results", []))
