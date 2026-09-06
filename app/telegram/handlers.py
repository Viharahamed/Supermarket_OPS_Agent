# app/telegram/handlers.py
"""Telegram Bot Handlers for Kirana AI Agent.

Handles Telegram updates, command handlers (/start, /help, /new), text message
routing to app.agent.handle_message(), safe HTML formatting, message splitting,
and error boundaries.
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import List

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.agent import handle_message, clear_session
from app.exceptions import (
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)

logger = logging.getLogger("app.telegram.handlers")


# -----------------------------------------------------------------------------
# Formatting & Message Splitting Helpers
# -----------------------------------------------------------------------------

def escape_html_text(text: str) -> str:
    """Safely escape special HTML characters in text."""
    if not text:
        return ""
    return html.escape(text)


def format_telegram_html(text: str) -> str:
    """Format agent output into Telegram-safe HTML.
    
    Converts markdown bold/italics/code fences into HTML tags while escaping
    raw HTML tags to avoid Telegram parsing errors.
    """
    if not text:
        return ""

    # Preserve markdown code blocks before escaping
    code_blocks: List[str] = []

    def save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(1))
        return f"___CODE_BLOCK_{len(code_blocks) - 1}___"

    # Extract code blocks ```...```
    text = re.sub(r"```(?:[a-zA-Z]*\n)?(.*?)```", save_code_block, text, flags=re.DOTALL)

    # Escape all HTML characters
    escaped = escape_html_text(text)

    # Convert markdown syntax to Telegram HTML tags
    # Bold **text** -> <b>text</b>
    escaped = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
    # Italic *text* or _text_ -> <i>text</i>
    escaped = re.sub(r"(?<!\w)\*(.*?)\*(?!\w)", r"<i>\1</i>", escaped)
    # Inline code `text` -> <code>text</code>
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    # Restore code blocks cleanly inside <pre> tags
    for i, code_content in enumerate(code_blocks):
        escaped_code = escape_html_text(code_content.strip())
        escaped = escaped.replace(f"___CODE_BLOCK_{i}___", f"<pre>{escaped_code}</pre>")

    return escaped


def split_message(text: str, max_length: int = 4000) -> List[str]:
    """Split long responses into chunks that fit within Telegram's 4096 char limit."""
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    lines = text.split("\n")
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # If a single line exceeds max_length, split it forcefully
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# -----------------------------------------------------------------------------
# Command Handlers (/start, /help, /new)
# -----------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - Onboard user & explain agent capabilities."""
    user = update.effective_user
    chat_id = update.effective_chat.id if update.effective_chat else None
    logger.info(f"Telegram /start command received from user_id={user.id if user else 'unknown'}, chat_id={chat_id}")

    welcome_text = (
        "<b>🏪 Welcome to Kirana AI Store Manager!</b>\n\n"
        "I am your automated AI store assistant. I can manage inventory, generate draft bills, "
        "record Khata customer credit payments, calculate GST taxes (₹), and deliver daily sales reports.\n\n"
        "<b>Available Commands:</b>\n"
        "• /start — Welcome overview & features\n"
        "• /help — Full usage guide & query examples\n"
        "• /new — Clear conversation session & start fresh\n\n"
        "<b>Example Queries:</b>\n"
        "• <i>\"Do we have Maggi or Sugar in stock?\"</i>\n"
        "• <i>\"Receive 50 packs of Fortune Oil 1L cost 110 MRP 145\"</i>\n"
        "• <i>\"Create a draft bill\"</i>\n"
        "• <i>\"What is Ramesh Kumar's Khata balance?\"</i>\n"
        "• <i>\"Show today's daily sales report\"</i>"
    )

    if update.message:
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - Comprehensive command reference & query list."""
    user = update.effective_user
    logger.info(f"Telegram /help command received from user_id={user.id if user else 'unknown'}")

    help_text = (
        "<b>📖 Kirana AI Agent Help & Usage Guide</b>\n\n"
        "<b>Commands:</b>\n"
        "• /start — Re-display welcome overview\n"
        "• /help — Show this reference guide\n"
        "• /new — Reset conversation context (Store catalog & financial data remain 100% safe!)\n\n"
        "<b>Inventory Commands:</b>\n"
        "• <i>Check stock:</i> \"How much Maggi is left?\"\n"
        "• <i>Low stock check:</i> \"Which products are low in stock?\"\n"
        "• <i>Receive stock:</i> \"Add 50 packets of Maggi, cost 12, MRP 14\"\n\n"
        "<b>Billing & Sales:</b>\n"
        "• <i>Start bill:</i> \"Make a bill for 2 sugar and 4 Maggi\"\n"
        "• <i>Edit bill:</i> \"Remove Maggi from the bill\"\n"
        "• <i>Finalize:</i> \"Finalize Bill #1 with cash\"\n\n"
        "<b>Khata Customer Ledger:</b>\n"
        "• <i>Check balance:</i> \"What is Ramesh's balance?\"\n"
        "• <i>Record payment:</i> \"Ramesh paid 300\"\n\n"
        "<b>Analytics & GST:</b>\n"
        "• <i>Sales summary:</i> \"What are today's sales?\"\n"
        "• <i>Tax report:</i> \"Show GST tax collections summary\""
    )

    if update.message:
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - Clear agent conversation session state."""
    user = update.effective_user
    user_id = user.id if user else 0
    logger.info(f"Telegram /new command received for session reset from user_id={user_id}")

    success = clear_session(user_id)
    if success:
        response = (
            "<b>✨ Fresh Agent Session Started!</b>\n\n"
            "Your conversation history has been reset.\n"
            "<i>(Note: All store products, stock levels, draft/finalized bills, customer Khata accounts, and preferences remain 100% safe in the database.)</i>"
        )
    else:
        response = "⚠️ Could not reset session history cleanly. Please try again."

    if update.message:
        await update.message.reply_text(response, parse_mode=ParseMode.HTML)


# -----------------------------------------------------------------------------
# Text Message Routing Handler
# -----------------------------------------------------------------------------

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route normal user text queries to app.agent.handle_message()."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else None
    chat_id = update.effective_chat.id if update.effective_chat else None

    logger.info(f"Incoming Telegram Message from user_id={user_id}, chat_id={chat_id}: '{user_text}'")
    start_time = time.time()

    try:
        # Route query to AI Agent Service Layer
        agent_response = handle_message(user_text, user_id=user_id)
        elapsed = time.time() - start_time
        logger.info(f"Agent processed message in {elapsed:.2f}s for user_id={user_id}")

        raw_content = agent_response.content or "No response generated."
        formatted_html = format_telegram_html(raw_content)

        # Split message into chunks if exceeding Telegram's character limit
        message_chunks = split_message(formatted_html)

        for chunk in message_chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
            except Exception as parse_err:
                logger.warning(f"Telegram HTML parse error: {parse_err}. Falling back to plain text reply.")
                # Fallback to plain text if HTML parsing failed for chunk
                plain_chunks = split_message(raw_content)
                for plain_chunk in plain_chunks:
                    await update.message.reply_text(plain_chunk)

    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error(f"Error handling Telegram message after {elapsed:.2f}s: {exc}", exc_info=True)
        await send_error_response(update, exc)


# -----------------------------------------------------------------------------
# Global Error Handling & Safe User Responses
# -----------------------------------------------------------------------------

async def send_error_response(update: Update, exc: Exception) -> None:
    """Send user-friendly error response without exposing sensitive internal details."""
    if not update.message:
        return

    if isinstance(exc, OllamaUnavailableError):
        msg = (
            "<b>⚠️ AI Service Unavailable</b>\n\n"
            "Could not connect to the local Ollama AI service. Please verify Ollama is running (`ollama serve`)."
        )
    elif isinstance(exc, OllamaTimeoutError):
        msg = (
            "<b>⏳ AI Request Timed Out</b>\n\n"
            "The AI model took too long to generate a response. Please simplify your query or try again."
        )
    elif isinstance(exc, ModelNotFoundError):
        msg = (
            "<b>❌ Model Not Found</b>\n\n"
            "The requested AI model is not installed in your local Ollama instance."
        )
    else:
        msg = (
            "<b>❌ Request Error</b>\n\n"
            "An error occurred while processing your query. Please try rephrasing your request."
        )

    try:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception:
        await update.message.reply_text("An error occurred while processing your request.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global Telegram error handler for unhandled framework exceptions."""
    logger.error(f"Unhandled Telegram exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await send_error_response(update, context.error if isinstance(context.error, Exception) else Exception(str(context.error)))
