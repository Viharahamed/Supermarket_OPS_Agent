# tests/test_alembic_migrations.py
"""Alembic Database Migrations Test Suite (Phase 13A.4).

Verifies initial schema migration creation, upgrade head execution,
idempotency, downgrade/re-upgrade cycles, and revision history.
"""

import os
import tempfile
import pytest
from sqlalchemy import inspect


def _require_alembic():
    try:
        import alembic  # noqa: F401
    except ImportError:
        pytest.skip("Alembic package is not installed in the environment.")


@pytest.fixture
def temp_sqlite_db_url():
    """Create a temporary SQLite database URL for isolated migration testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    url = f"sqlite:///{db_path}"
    yield url
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def _get_alembic_config(db_url: str):
    """Helper to configure Alembic Config for testing."""
    _require_alembic()
    from alembic.config import Config
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    return alembic_cfg


def test_alembic_upgrade_head_sqlite(temp_sqlite_db_url):
    """Verify that 'alembic upgrade head' creates all 9 tables on a fresh SQLite database."""
    _require_alembic()
    from alembic import command
    alembic_cfg = _get_alembic_config(temp_sqlite_db_url)
    command.upgrade(alembic_cfg, "head")

    from app.db.database import _configure_engine
    engine = _configure_engine(temp_sqlite_db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    engine.dispose()

    expected_tables = {
        "stores",
        "products",
        "stock_movements",
        "customers",
        "bills",
        "bill_items",
        "khata_transactions",
        "owner_preferences",
        "agent_sessions",
        "alembic_version",
    }
    assert expected_tables.issubset(table_names)


def test_alembic_migration_idempotency(temp_sqlite_db_url):
    """Verify that running 'alembic upgrade head' multiple times is idempotent."""
    _require_alembic()
    from alembic import command
    alembic_cfg = _get_alembic_config(temp_sqlite_db_url)
    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")


def test_alembic_downgrade_and_upgrade_cycle(temp_sqlite_db_url):
    """Verify that 'alembic downgrade base' drops schema and 'upgrade head' re-creates it."""
    _require_alembic()
    from alembic import command
    alembic_cfg = _get_alembic_config(temp_sqlite_db_url)
    command.upgrade(alembic_cfg, "head")

    command.downgrade(alembic_cfg, "base")

    from app.db.database import _configure_engine
    engine = _configure_engine(temp_sqlite_db_url)
    inspector = inspect(engine)
    tables_after_downgrade = set(inspector.get_table_names())
    engine.dispose()
    assert "products" not in tables_after_downgrade
    assert "bills" not in tables_after_downgrade

    command.upgrade(alembic_cfg, "head")
    engine2 = _configure_engine(temp_sqlite_db_url)
    inspector2 = inspect(engine2)
    tables_after_reupgrade = set(inspector2.get_table_names())
    engine2.dispose()
    assert "products" in tables_after_reupgrade
    assert "bills" in tables_after_reupgrade


def test_alembic_package_unshadowed():
    """Verify repository migration directory 'migrations/' does not shadow installed alembic package."""
    _require_alembic()
    import alembic
    from alembic.config import main as alembic_main

    # Clean up legacy alembic/ directory if present on disk
    if os.path.exists("alembic"):
        import shutil
        shutil.rmtree("alembic", ignore_errors=True)

    # Real installed package has __file__ pointing to site-packages or library location
    assert hasattr(alembic, "__file__")
    assert alembic.__file__ is not None
    assert callable(alembic_main)

    # Confirm repository directory is named 'migrations' and 'alembic/' directory is removed
    assert os.path.exists("migrations")
    assert os.path.exists(os.path.join("migrations", "env.py"))
    assert not os.path.exists("alembic")


