from sqlalchemy.orm import Session
from datetime import datetime, timezone
from src.models.debate import DebateSession, Turn, SpeakerType
from src.models.setup import Motion, AICallLog
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


def create_turn(
    db: Session,
    session_id: str,
    turn_number: int,
    speaker_role: str,
    speaker_type: str,
    transcript_text: str,
    duration_seconds: int = 0
) -> Turn:
    """Creates a new turn record in the database."""
    turn = Turn(
        session_id=session_id,
        turn_number=turn_number,
        speaker_role=speaker_role,
        speaker_type=speaker_type,
        transcript_text=transcript_text,
        duration_seconds=duration_seconds,
        started_at=datetime.now(timezone.utc)
    )
    
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


def log_ai_call(
    db: Session,
    session_id: str,
    agent_name: str,
    prompt_used: str,
    model_version: str,
    temperature: float,
    raw_output: str
) -> AICallLog:
    """Logs AI agent call to database for observability."""
    ai_log = AICallLog(
        session_id=session_id,
        agent_name=agent_name,
        prompt_used=prompt_used,
        model_version=model_version,
        temperature=temperature,
        raw_output=raw_output
    )
    
    db.add(ai_log)
    db.commit()
    db.refresh(ai_log)
    return ai_log