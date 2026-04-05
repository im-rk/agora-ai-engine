import pytest 
import uuid
from datetime import datetime,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,Session
from unittest.mock import Mock,AsyncMock,patch, MagicMock

from src.core.database import Base
from src.models.user import User,SkillLevel
from src.models.setup import Motion, MotionCategory, CasePrep, AICallLog
from src.models.debate import DebateSession,MatchFormat,MatchStatus
from src.schemas.debate_schema import MatchStartRequest,MatchStartResponse

#------------------
# Database setup (mock db)
#------------------

@pytest.fixture(scope="session")
def engine():
    """Create test databae (SQLite in-memory). Runs once per test sesison."""
    engine=create_engine("sqlite:///:memory",echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(engine):
    """Fresh database session for each test.Auto rolls back after."""
    session=sessionmaker(bind=engine)
    session=Session()
    yield session
    session.rollback()
    session.close()

#------------------------
#user fixtures
#------------------------

@pytest.fixture
def sample_user(db_session:Session)->User:
    """Create a test user in database."""
    user=User(
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

#-------------------------
#Motion fixture
#------------------------
@pytest.fixture
def sample_motion(db_session:Session)->Motion:
    """create a test motion"""
    motion=Motion(
        id=uuid.uuid4(),
        motion_text="This house would ban social media for users under 16",
        category=MotionCategory.TECHNOLOGY,
        is_custom=True
    )

    db_session.add(motion)
    db_session.commit()
    return motion

#-------------------------
#case prep fixtures
#-------------------------
@pytest.fixture
def sample_case_prep(db_session:Session,sample_user:User,sample_motion: Motion) -> CasePrep:
    prep=CasePrep(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        motion_id=sample_motion.id,
        side="Government"
    )
    db_session.add(prep)
    db_session.commit()
    return prep

#--------------------------
# debate session fixtures
#--------------------------

@pytest.fixture
def sample_debate_session(
    db_session: Session,
    sample_user: User,
    sample_motion: Motion,
    sample_case_prep: CasePrep
)->DebateSession:
    """Create debate session."""
    session=DebateSession(
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

#------------------------
# api request fixtures
#------------------------
@pytest.fixture
def match_start_request(sample_user:User) -> MatchStartRequest:
    """Sample match start request"""
    return MatchStartRequest(
        user_id=str(sample_user.id),
        motion_text="This House would ban social media for users under 16",
        side="Government",
        format="British Parlimentary"
    )

#--------------------------
# ai response fixtures
#--------------------------
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