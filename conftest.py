import sys
import os
from unittest.mock import patch
import pytest
from sqlalchemy.orm import sessionmaker

# Add root project directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Ensure test environment uses in-memory SQLite database to prevent schema conflicts with legacy disk DBs
TEST_DB_URL = "sqlite:///file:memdb_test?mode=memory&cache=shared&uri=true"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.db.database import Base, _configure_engine
from app.auth.service import bootstrap_store_and_user

# Create shared in-memory test engine
test_engine = _configure_engine(TEST_DB_URL)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# Ensure default store and owner user exist on the shared test engine
with TestingSessionLocal() as session:
    bootstrap_store_and_user(db=session)


@pytest.fixture(autouse=True)
def _patch_global_db():
    """Autouse fixture patching database engine and SessionLocal for all tests."""
    with patch("app.db.database.engine", test_engine), \
         patch("app.db.database.SessionLocal", TestingSessionLocal):
        yield


@pytest.fixture
def db_session():
    """Global fixture providing an isolated database session for unit and integration tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


