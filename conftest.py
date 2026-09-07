import sys
import os
from unittest.mock import patch
import pytest
from sqlalchemy.orm import sessionmaker

# Add root project directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.database import Base, _configure_engine


@pytest.fixture
def db_session():
    """Global fixture providing an isolated in-memory SQLite database session for unit and integration tests."""
    engine = _configure_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with patch("app.db.database.SessionLocal", TestingSessionLocal), \
         patch("app.db.database.engine", engine):
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)
