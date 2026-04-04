from sqlalchemy.orm import Session
from src.models.debate import DebateSession
from src.models.setup import Motion
from src.models.user import SkillLevel


def create_debate_session(
    db: Session,
    user_id: str,
    motion_id: str,
    format_type: str,
    side: str,
    skill_level: SkillLevel
) -> DebateSession:
    """Creates a new debate session in the database."""
    new_session = DebateSession(
        user_id=user_id,
        motion_id=motion_id,
        format=format_type,
        human_role=side,
        skill_level=skill_level
    )

    db.add(new_session)
    db.flush()
    return new_session