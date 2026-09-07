import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Prepend application root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings
from app.db.database import Base, _configure_engine
# Import all ORM models to ensure they register on Base.metadata
import app.db.models  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Set database URL dynamically from central application settings or test environment if not already specified
existing_url = config.get_main_option("sqlalchemy.url")
if not existing_url:
    settings = get_settings()
    db_url = os.getenv("POSTGRES_TEST_URL") or settings.database_url
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Check if a custom connection was injected into config.attributes (e.g. during test runs)
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        url = config.get_main_option("sqlalchemy.url")
        connectable = _configure_engine(url)

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=url.startswith("sqlite"),
            )
            with context.begin_transaction():
                context.run_migrations()
    else:
        url = str(connectable.engine.url)
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
