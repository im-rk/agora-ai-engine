"""
Shared pytest fixtures for the entire test suite.
This is the ENGINE - it sets up your test database and FastAPI client.
All fixtures work for both unit and integration tests.
"""
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from src.core.database import Base
from src.models.user import User, SkillLevel
from src.models.setup import Motion, MotionCategory, CasePrep, AICallLog
from src.models.debate import DebateSession, MatchFormat, MatchStatus
from src.schemas.debate_schema import MatchStartRequest
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


# ============================================================================
# USER & BASIC FIXTURES
# ============================================================================

@pytest.fixture
def sample_user(db_session: Session):
    """Create a test user in the database."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        display_name="Test User",
        skill_level=SkillLevel.INTERMEDIATE
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_user_data():
    """Sample user data for API requests (not in DB yet)."""
    return {
        "email": "newuser@example.com",
        "password": "SecurePass123!",
        "display_name": "New Test User",
        "skill_level": "Intermediate"
    }


# ============================================================================
# MOTION & CASE PREP FIXTURES
# ============================================================================

@pytest.fixture
def sample_motion(db_session: Session):
    """Create a test motion in the database."""
    motion = Motion(
        id=uuid.uuid4(),
        motion_text="This House would ban social media for users under 16",
        category=MotionCategory.TECHNOLOGY,
        is_custom=True
    )
    db_session.add(motion)
    db_session.commit()
    return motion


@pytest.fixture
def sample_case_prep(db_session: Session, sample_user: User, sample_motion: Motion):
    """Create an empty case prep (before AI fills it)."""
    prep = CasePrep(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        motion_id=sample_motion.id,
        side="Government"
    )
    db_session.add(prep)
    db_session.commit()
    return prep


@pytest.fixture
def sample_debate_session(db_session: Session, sample_user: User, sample_motion: Motion, sample_case_prep: CasePrep):
    """Create a debate session linked to user and motion."""
    session = DebateSession(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        motion_id=sample_motion.id,
        case_prep_id=sample_case_prep.id,
        format=MatchFormat.BRITISH_PARLIAMENTARY,
        human_role="Government",
        skill_level=SkillLevel.INTERMEDIATE,
        status=MatchStatus.STARTED
    )
    db_session.add(session)
    db_session.commit()
    return session


# ============================================================================
# API REQUEST FIXTURES
# ============================================================================

@pytest.fixture
def match_start_request(sample_user: User):
    """Sample request to start a match."""
    return MatchStartRequest(
        user_id=str(sample_user.id),
        motion_text="This House would ban social media for users under 16",
        side="Government",
        format="British Parliamentary"
    )


# ============================================================================
# AI RESPONSE FIXTURES
# ============================================================================

@pytest.fixture
def mock_ai_response():
    """Mock response from OpenAI (what prep_coach returns)."""
    return {
        "model_definition": "Government's core contention is that social media poses severe risks to minors.",
        "arguments": [
            {
                "claim": "Social media harms mental health of teenagers",
                "reasoning": "Research shows increased depression and anxiety rates",
                "impact": "Banning protects youth wellbeing"
            },
            {
                "claim": "Platforms exploit youth through algorithms",
                "reasoning": "Designed to maximize engagement, not wellbeing",
                "impact": "Reduces manipulation of vulnerable populations"
            },
            {
                "claim": "Early exposure to social media impairs development",
                "reasoning": "Critical developmental period disrupted",
                "impact": "Preserves healthy cognitive development"
            }
        ],
        "counter_arguments": [
            "Opposition will argue social media enables free speech and community",
            "They will claim banning infringes on parental choice"
        ],
        "evidence": [
            "2023 US Surgeon General's advisory on social media mental health risks",
            "Stanford study: 47% of teens report social media stress",
            "Meta internal docs show platform design targets vulnerabilities"
        ]
    }


@pytest.fixture
def invalid_ai_response():
    """Mock invalid AI response (missing required fields)."""
    return {
        "model_definition": "...",
        "arguments": [{"claim": "..."}]
        # Missing: counter_arguments, evidence
    }


# ============================================================================
# MOCKING FIXTURES
# ============================================================================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns structured output."""
    mock_client = AsyncMock()
    mock_structured = AsyncMock()
    
    # Mock the ainvoke method
    mock_structured.ainvoke = AsyncMock()
    
    # Mock with_structured_output to return the mock_structured
    mock_client.with_structured_output = Mock(return_value=mock_structured)
    
    return mock_client


@pytest.fixture
def mock_get_openai_client(mock_openai_client):
    """Patch get_openai_client to return mock."""
    with patch("src.ai.clients.openai_client.get_openai_client") as mock:
        mock.return_value = mock_openai_client
        yield mock


@pytest.fixture
def mock_prompt_template():
    """Mock LangChain prompt template."""
    mock_prompt = Mock()
    mock_prompt.__or__ = Mock(return_value=Mock())  # Support | operator
    return mock_prompt


@pytest.fixture
def mock_get_prompt(mock_prompt_template):
    """Patch get_prep_coach_prompt to return mock."""
    with patch("src.ai.prompts.prep_coach_prompts.get_prep_coach_prompt") as mock:
        mock.return_value = mock_prompt_template
        yield mock


# ============================================================================
# PYDANTIC SCHEMA FIXTURES (for structured output)
# ============================================================================

@pytest.fixture
def mock_ai_prep_result(mock_ai_response):
    """Mock Pydantic AIPrepResult object."""
    from src.schemas.prep_coach_schema import AIPrepResult
    
    return AIPrepResult(
        model_definition=mock_ai_response["model_definition"],
        arguments=[
            type('Argument', (), {'claim': arg['claim'], 'reasoning': arg['reasoning'], 'impact': arg['impact']})()
            for arg in mock_ai_response["arguments"]
        ],
        counter_arguments=mock_ai_response["counter_arguments"],
        evidence=mock_ai_response["evidence"]
    )
