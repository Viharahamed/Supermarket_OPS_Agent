from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import Settings, get_settings

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.x declarative ORM models."""
    pass

def _configure_engine(db_url_or_settings: str | Settings | None = None) -> Engine:
    if isinstance(db_url_or_settings, Settings):
        cfg = db_url_or_settings
        url = cfg.database_url
    elif isinstance(db_url_or_settings, str):
        cfg = get_settings()
        url = db_url_or_settings
    else:
        cfg = get_settings()
        url = cfg.database_url

    # Normalize Railway postgres:// or standard postgresql:// to use psycopg v3 dialect
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 15}
        if "uri=true" in url.lower() or "mode=memory" in url.lower() or "cache=shared" in url.lower():
            connect_args["uri"] = True

        from sqlalchemy.pool import NullPool, StaticPool
        if "mode=memory" in url.lower() or ":memory:" in url.lower():
            pool_cls = StaticPool
        else:
            pool_cls = NullPool

        engine = create_engine(
            url,
            connect_args=connect_args,
            poolclass=pool_cls,
            echo=False,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        return engine


    # PostgreSQL or other relational database dialects
    return create_engine(
        url,
        pool_size=cfg.db_pool_size,
        max_overflow=cfg.db_max_overflow,
        pool_timeout=cfg.db_pool_timeout,
        pool_recycle=cfg.db_pool_recycle,
        pool_pre_ping=cfg.db_pool_pre_ping,
        echo=False,
    )

settings = get_settings()

# Ensure target directory exists for sqlite file
if settings.database_url.startswith("sqlite:///./"):
    relative_path = settings.database_url.replace("sqlite:///./", "")
    dir_path = os.path.dirname(relative_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

engine = _configure_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(target_engine=None):
    """Create all database tables."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

@contextmanager
def get_db_context(target_sessionmaker=None) -> Generator[Session, None, None]:
    """Context manager for managing database session lifecycle."""
    sm = target_sessionmaker or SessionLocal
    db = sm()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_db() -> Generator[Session, None, None]:
    """Dependency generator for FastAPI/services session injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
