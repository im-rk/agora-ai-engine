"""
Shared pytest fixtures for the entire test suite.
Central hub for database setup, test data, and mocks.
"""
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.core.database import Base
from src.models.user import User, SkillLevel
from src.models.setup import Motion, MotionCategory, CasePrep, AICallLog
from src.models.debate import DebateSession, MatchFormat, MatchStatus
from src.schemas.debate_schema import MatchStartRequest


# ============================================================================
# DATABASE SETUP
# ============================================================================

@pytest.fixture(scope="session")
def engine():
    """Create test database (SQLite in-memory). Runs once per test session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Fresh database session for each test. Auto-rolls back after."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ============================================================================
# USER FIXTURES
# ============================================================================

@pytest.fixture
def sample_user(db_session: Session) -> User:
    """Create a test user in database."""
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
def sample_user_data() -> dict:
    """Sample user data for API requests."""
    return {
        "email": "newuser@example.com",
        "password": "SecurePass123!",
        "display_name": "New Test User",
        "skill_level": "Intermediate"
    }


# ============================================================================
# MOTION FIXTURES
# ============================================================================

@pytest.fixture
def sample_motion(db_session: Session) -> Motion:
    """Create a test motion."""
    motion = Motion(
        id=uuid.uuid4(),
        motion_text="This House would ban social media for users under 16",
        category=MotionCategory.TECHNOLOGY,
        is_custom=True
    )
    db_session.add(motion)
    db_session.commit()
    return motion


# ============================================================================
# CASE PREP FIXTURES
# ============================================================================

@pytest.fixture
def sample_case_prep(db_session: Session, sample_user: User, sample_motion: Motion) -> CasePrep:
    """Create empty case prep (before AI generation)."""
    prep = CasePrep(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        motion_id=sample_motion.id,
        side="Government"
    )
    db_session.add(prep)
    db_session.commit()
    return prep


# ============================================================================
# DEBATE SESSION FIXTURES
# ============================================================================

@pytest.fixture
def sample_debate_session(
    db_session: Session,
    sample_user: User,
    sample_motion: Motion,
    sample_case_prep: CasePrep
) -> DebateSession:
    """Create debate session."""
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
def match_start_request(sample_user: User) -> MatchStartRequest:
    """Sample match start request."""
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
def mock_ai_response() -> dict:
    """Valid AI response from OpenAI."""
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
def invalid_ai_response() -> dict:
    """Invalid AI response (missing required fields)."""
    return {
        "model_definition": "...",
        "arguments": [{"claim": "..."}]
    }


# ============================================================================
# PYDANTIC SCHEMA FIXTURES
# ============================================================================

@pytest.fixture
def mock_ai_prep_result(mock_ai_response: dict):
    """Mock AIPrepResult Pydantic object."""
    from src.schemas.prep_coach_schema import AIPrepResult, Argument
    
    arguments = [
        Argument(**arg) for arg in mock_ai_response["arguments"]
    ]
    
    return AIPrepResult(
        model_definition=mock_ai_response["model_definition"],
        arguments=arguments,
        counter_arguments=mock_ai_response["counter_arguments"],
        evidence=mock_ai_response["evidence"]
    )


# ============================================================================
# OPENAI CLIENT MOCKS
# ============================================================================

@pytest.fixture
def mock_openai_client():
    """Mock ChatOpenAI client with structured output."""
    mock_client = AsyncMock()
    mock_structured = AsyncMock()
    mock_structured.ainvoke = AsyncMock()
    mock_client.with_structured_output = Mock(return_value=mock_structured)
    return mock_client


@pytest.fixture
def mock_get_openai_client(mock_openai_client):
    """Patch get_openai_client to return mock."""
    with patch("src.ai.clients.openai_client.get_openai_client") as mock:
        mock.return_value = mock_openai_client
        yield mock


# ============================================================================
# LANGCHAIN PROMPT MOCKS
# ============================================================================

@pytest.fixture
def mock_prompt_template():
    """Mock LangChain ChatPromptTemplate."""
    mock_prompt = MagicMock()
    return mock_prompt


@pytest.fixture
def mock_get_prompt(mock_prompt_template):
    """Patch get_prep_coach_prompt to return mock."""
    with patch("src.ai.prompts.prep_coach_prompts.get_prep_coach_prompt") as mock:
        mock.return_value = mock_prompt_template
        yield mock


# ============================================================================
# SERVICE MOCKS
# ============================================================================

@pytest.fixture
def mock_prepare_case():
    """Mock prepare_case service function."""
    return AsyncMock()


@pytest.fixture
def mock_start_new_match():
    """Mock start_new_match service function."""
    return AsyncMock()


# ============================================================================
# REPOSITORY MOCKS
# ============================================================================

@pytest.fixture
def mock_case_prep_repo():
    """Mock case prep repository."""
    mock_repo = MagicMock()
    mock_repo.create_case_prep = AsyncMock()
    mock_repo.get_case_prep_by_id = AsyncMock()
    mock_repo.get_case_prep_by_match = AsyncMock()
    mock_repo.update_case_prep = AsyncMock()
    mock_repo.save_ai_call_log = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_debate_repo():
    """Mock debate repository."""
    mock_repo = MagicMock()
    mock_repo.create_debate_session = AsyncMock()
    mock_repo.get_debate_session = AsyncMock()
    mock_repo.update_debate_status = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_user_repo():
    """Mock user repository."""
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock()
    mock_repo.create = AsyncMock()
    mock_repo.update = AsyncMock()
    return mock_repo