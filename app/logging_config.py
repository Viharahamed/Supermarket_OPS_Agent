# app/logging_config.py
"""Structured Application Logging & Lightweight Request Correlation.

Provides contextvar-backed correlation ID propagation, sensitive secret masking,
and validated log level setup for the Kirana AI Agent system.
"""

from __future__ import annotations

import contextvars
import logging
import re
import sys
from typing import Optional

# Lightweight process-safe correlation ID context variable
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> Optional[str]:
    """Retrieve the current thread/async task correlation ID if available."""
    return correlation_id_ctx.get()


def set_correlation_id(corr_id: str) -> None:
    """Set correlation ID for the current execution context."""
    correlation_id_ctx.set(corr_id)


def clear_correlation_id() -> None:
    """Reset correlation ID context to None."""
    correlation_id_ctx.set(None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects correlation ID into LogRecords."""

    def filter(self, record: logging.LogRecord) -> bool:
        corr_id = get_correlation_id()
        record.correlation_id = corr_id if corr_id else "system"
        return True


class SecretMaskingFormatter(logging.Formatter):
    """Logging Formatter that automatically redacts sensitive tokens, secrets, and credentials."""

    SECRET_PATTERNS = [
        # Match Telegram bot token format (e.g., 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ...)
        (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,50}\b"), "[REDACTED_TELEGRAM_TOKEN]"),
        # Match OpenRouter API Key format (e.g., sk-or-v1-...)
        (re.compile(r"sk-or-v1-[a-zA-Z0-9]{30,80}"), "[REDACTED_OPENROUTER_KEY]"),
        # Match Database connection URLs with passwords
        (
            re.compile(r"(postgres(?:ql)?(?:\+[a-z0-9]+)?://[^:]+:)([^@]+)(@.+)"),
            r"\1***MASKED***\3",
        ),
    ]

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern, replacement in self.SECRET_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        return formatted


ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def validate_log_level(level_str: str) -> str:
    """Validate and normalize log level string.

    Raises:
        ValueError: If log level string is invalid.
    """
    if not isinstance(level_str, str):
        raise ValueError(f"Invalid log level type '{type(level_str)}'. Expected string.")

    normalized = level_str.strip().upper()
    if normalized not in ALLOWED_LOG_LEVELS:
        raise ValueError(
            f"Invalid LOG_LEVEL '{level_str}'. Must be one of: {sorted(ALLOWED_LOG_LEVELS)}"
        )
    return normalized


def setup_logging(log_level_str: str = "INFO", app_env: str = "development") -> None:
    """Configure root logger with structured correlation formatting and secret masking.

    Args:
        log_level_str: Target log level string (e.g. 'INFO', 'DEBUG').
        app_env: Target environment ('production', 'development', 'test').
    """
    validated_level = validate_log_level(log_level_str)

    # In production, default level must not be DEBUG
    if app_env.strip().lower() == "production" and validated_level == "DEBUG":
        logging.warning("DEBUG log level requested in production. Resetting to INFO for security.")
        validated_level = "INFO"

    numeric_level = getattr(logging, validated_level)

    # Custom log line format including correlation ID
    fmt = "[%(asctime)s] [%(levelname)s] [corr_id=%(correlation_id)s] %(name)s: %(message)s"
    formatter = SecretMaskingFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to prevent duplicate output
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root_logger.addHandler(handler)
