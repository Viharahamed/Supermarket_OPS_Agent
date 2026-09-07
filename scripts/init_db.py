# scripts/init_db.py
"""Explicit Database Initialization Script for Kirana AI Agent.

Creates all SQLAlchemy database tables defined in app.db.models against
the target DATABASE_URL (SQLite or PostgreSQL) without using Alembic.
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect
from app.config import get_settings
from app.db.database import Base, _configure_engine
import app.db.models  # Ensures all ORM models are registered with Base.metadata

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("init_db")


def mask_db_url(url: str) -> str:
    """Return database URL with password masked for secure logging."""
    if "@" in url:
        try:
            proto, rest = url.split("://", 1)
            user_pass, host_db = rest.split("@", 1)
            if ":" in user_pass:
                user = user_pass.split(":", 1)[0]
                return f"{proto}://{user}:***MASKED***@{host_db}"
            return f"{proto}://***MASKED***@{host_db}"
        except Exception:
            return "***MASKED_DB_URL***"
    return url


def run_init_db(custom_db_url: str | None = None) -> bool:
    """Initialize database tables explicitly using Base.metadata.create_all().

    Args:
        custom_db_url: Optional override database URL. Defaults to central settings.

    Returns:
        True if database tables were successfully created/verified, False otherwise.
    """
    settings = get_settings()
    db_url = custom_db_url or os.getenv("DATABASE_URL") or settings.database_url

    masked_url = mask_db_url(db_url)
    logger.info(f"Starting explicit database initialization for target: {masked_url}")

    try:
        # Configure engine using centralized application engine factory
        engine = _configure_engine(db_url)

        # Inspect registered metadata models
        registered_tables = list(Base.metadata.tables.keys())
        logger.info(f"Registered ORM model tables ({len(registered_tables)}): {sorted(registered_tables)}")

        # Create missing database tables
        Base.metadata.create_all(bind=engine)

        # Inspect engine tables to verify successful creation
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        engine.dispose()

        expected_tables = {
            "stores",
            "users",
            "products",
            "stock_movements",
            "customers",
            "bills",
            "bill_items",
            "khata_transactions",
            "owner_preferences",
            "agent_sessions",
        }

        missing_tables = expected_tables - existing_tables
        if missing_tables:
            logger.error(f"❌ Database initialization check failed! Missing tables: {missing_tables}")
            return False

        logger.info(f"✅ Database tables initialized successfully! Active tables: {sorted(existing_tables)}")
        return True

    except Exception as exc:
        logger.error(f"❌ Database initialization failed with exception: {exc}", exc_info=True)
        return False


def main() -> None:
    print("=" * 60)
    print("  🚀 KIRANA AI AGENT — DATABASE INITIALIZATION SCRIPT")
    print("=" * 60)

    success = run_init_db()
    if not success:
        print("\n❌ Error initializing database tables.")
        sys.exit(1)

    print("\n✅ Database initialization complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
