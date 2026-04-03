"""
Shared pytest fixtures for the entire test suite.
This is the most important file - all fixtures defined here are available to all tests.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.database import Base


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine (in-memory SQLite for speed)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a new database session for each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


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
