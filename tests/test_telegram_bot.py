# tests/test_telegram_bot.py
"""Test suite for Phase 12 Telegram Bot Integration.

Tests:
1. Telegram /start command.
2. Telegram /help command.
3. Telegram /new command session reset (without deleting catalog/stock/Khata data).
4. Text message routing to handle_message().
5. Safe HTML formatting and escaping.
6. Long message splitting (>4096 chars).
7. Application error handling & error boundary responses.
8. Ollama infrastructure error resilience.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.schemas import AgentResponse
from app.db.database import get_db_context
from app.db.models import Product, Customer, AgentSession
from app.exceptions import (
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from app.telegram.bot import build_application
from app.telegram.handlers import (
    escape_html_text,
    format_telegram_html,
    help_command,
    new_command,
    send_error_response,
    split_message,
    start_command,
    text_message_handler,
)


# -----------------------------------------------------------------------------
# 1. HTML Formatting & Splitting Helpers
# -----------------------------------------------------------------------------

def test_escape_html_text():
    """Verify raw HTML special characters are escaped safely."""
    raw = "Maggi & Sugar <1kg> > 0"
    escaped = escape_html_text(raw)
    assert escaped == "Maggi &amp; Sugar &lt;1kg&gt; &gt; 0"


def test_format_telegram_html_markdown_conversion():
    """Verify markdown bold, italics, inline code, and code blocks convert to valid HTML tags."""
    md_text = "**Header Bold**\nCheck `search_products` for *details*:\n```json\n{\"stock\": 10}\n```"
    formatted = format_telegram_html(md_text)

    assert "<b>Header Bold</b>" in formatted
    assert "<code>search_products</code>" in formatted
    assert "<i>details</i>" in formatted
    assert "<pre>" in formatted
    assert "&quot;stock&quot;: 10" in formatted or '"stock": 10' in formatted


def test_split_message_under_limit():
    """Verify short text under max limit returns a single item list."""
    text = "Short text message"
    chunks = split_message(text, max_length=100)
    assert chunks == ["Short text message"]


def test_split_message_over_limit():
    """Verify long text splitting splits cleanly along line boundaries."""
    lines = [f"Line {i}: " + "x" * 50 for i in range(100)]
    long_text = "\n".join(lines)
    chunks = split_message(long_text, max_length=500)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 500


# -----------------------------------------------------------------------------
# 2. Command Handlers (/start, /help, /new)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_command_response():
    """Verify /start command sends welcoming greeting with HTML parse mode."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    sent_text = update.message.reply_text.call_args[0][0]
    assert "Welcome to Kirana AI Store Manager" in sent_text
    assert update.message.reply_text.call_args[1]["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_help_command_response():
    """Verify /help command returns guide with commands & query examples."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await help_command(update, context)

    update.message.reply_text.assert_called_once()
    sent_text = update.message.reply_text.call_args[0][0]
    assert "Kirana AI Agent Help & Usage Guide" in sent_text
    assert "/new" in sent_text


@pytest.mark.asyncio
async def test_new_command_resets_session_without_deleting_store_data():
    """Verify /new resets conversation history while keeping catalog, stock, & Khata intact."""
    import uuid
    test_user_id = int(str(uuid.uuid4().int)[:8])
    unique_sku = f"TELE-{uuid.uuid4().hex[:6].upper()}"
    unique_phone = f"99{uuid.uuid4().hex[:8]}"[:10]

    with get_db_context() as db:
        # Seed test catalog product, customer, and session history
        prod = Product(
            sku=unique_sku,
            name="Telegram Test Product",
            cost_price=Decimal("10.00"),
            selling_price=Decimal("14.00"),
            mrp=Decimal("14.00"),
            stock_quantity=Decimal("50.00"),
            active=True,
        )
        cust = Customer(name="Telegram Customer", phone=unique_phone, khata_balance=Decimal("200.00"))
        session = AgentSession(user_id=test_user_id, history_json='[{"role": "user", "content": "hi"}]')
        
        db.add_all([prod, cust, session])
        db.commit()
        prod_id = prod.id
        cust_id = cust.id

    # Execute /new command
    update = MagicMock()
    update.effective_user.id = test_user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await new_command(update, context)

    update.message.reply_text.assert_called_once()
    assert "Fresh Agent Session Started" in update.message.reply_text.call_args[0][0]

    # Verify session cleared while product and customer remain intact
    with get_db_context() as db:
        session_after = db.query(AgentSession).filter_by(user_id=test_user_id).first()
        assert session_after is None  # Session cleared!

        prod_after = db.query(Product).filter_by(id=prod_id).first()
        assert prod_after is not None  # Product untouched!
        assert prod_after.stock_quantity == Decimal("50.00")

        cust_after = db.query(Customer).filter_by(id=cust_id).first()
        assert cust_after is not None  # Customer untouched!
        assert cust_after.khata_balance == Decimal("200.00")


# -----------------------------------------------------------------------------
# 3. Message Routing & Exception Boundaries
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_message_handler_routing():
    """Verify normal text messages are routed to app.agent.handle_message()."""
    update = MagicMock()
    update.message.text = "How much Maggi is left?"
    update.effective_user.id = 12345
    update.effective_chat.id = 67890
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    with patch("app.telegram.handlers.handle_message") as mock_handle:
        mock_handle.return_value = AgentResponse(
            content="We have 120 packs of Maggi 70g in stock.",
            metadata={"iterations": 2},
        )

        await text_message_handler(update, context)

        mock_handle.assert_called_once_with("How much Maggi is left?", user_id=12345)
        update.message.reply_text.assert_called_once()
        assert "120 packs of Maggi" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_obj, expected_keyword", [
    (OllamaUnavailableError("Service down"), "AI Service"),
    (OllamaTimeoutError("Request timed out"), "timed out"),
    (ModelNotFoundError("qwen3:8b"), "not found"),
    (Exception("Generic application error"), "error occurred"),
])
async def test_send_error_response_boundaries(exception_obj, expected_keyword):
    """Verify exception handlers return clean, safe error messages without stack traces."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()

    await send_error_response(update, exception_obj)

    update.message.reply_text.assert_called_once()
    sent_text = update.message.reply_text.call_args[0][0]
    assert expected_keyword.lower() in sent_text.lower()
    assert "Traceback" not in sent_text
    assert "SELECT" not in sent_text


def test_build_application_missing_token_rejection():
    """Verify build_application raises ValueError when TELEGRAM_BOT_TOKEN is missing."""
    with patch("app.telegram.bot.get_settings") as mock_settings:
        mock_settings.return_value.telegram_bot_token = ""
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}):
            with pytest.raises(ValueError) as exc_info:
                build_application()
            assert "TELEGRAM_BOT_TOKEN is missing" in str(exc_info.value)
