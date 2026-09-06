import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import get_settings

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.x declarative ORM models."""
    pass

def _configure_engine(db_url: str):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False
    )

    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine

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
