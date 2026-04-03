"""
Shared pytest fixtures for the entire test suite.
This is the ENGINE - it sets up your test database and FastAPI client.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.core.database import Base
# from main import app  # TODO: Uncomment when main.py has FastAPI app


@pytest.fixture(scope="session")
def engine():
    """
    Create a test database engine (SQLite in-memory for speed).
    This runs ONCE per test session.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Create a fresh database session for EACH test.
    Automatically rolls back after each test to keep tests isolated.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# @pytest.fixture
# def client():
#     """
#     FastAPI TestClient for integration tests.
#     TODO: Uncomment when main.py has FastAPI app
#     """
#     return TestClient(app)


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "SecurePass123!",
        "display_name": "Test User",
        "skill_level": "Intermediate"
    }


@pytest.fixture
def sample_motion():
    """Sample debate motion for testing."""
    return {
        "motion_text": "This House would ban social media for users under 16",
        "category": "Technology",
        "is_custom": False
    }
