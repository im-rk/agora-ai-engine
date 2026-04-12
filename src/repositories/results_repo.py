"""
Results Repository — Database operations for adjudication results.

Functions here are called by grading_service.py (Step 4D)
and results API (Step 5).
"""

import uuid
from sqlalchemy.orm import Session

from src.models.results import AdjudicationResult, UserPerformance


def save_adjudication_result(
    db: Session,
    session_id: str,
    winning_team: str,
    gov_total_score: float,
    opp_total_score: float,
    clash_table: list,
    speaker_scores: list,
) -> AdjudicationResult:
    """
    Save the full adjudication verdict to the database.
    Called once per match when adjudication completes.
    """
    result = AdjudicationResult(
        id=uuid.uuid4(),
        session_id=session_id,
        winning_team=winning_team,
        gov_total_score=gov_total_score,
        opp_total_score=opp_total_score,
        clash_table=clash_table,        # stored as JSONB in Postgres
        speaker_scores=speaker_scores,  # stored as JSONB in Postgres
    )
    db.add(result)
    db.commit()
    return result


def save_user_performance(
    db: Session,
    user_id: str,
    session_id: str,
    speaker_score_data: dict,
) -> UserPerformance:
    """
    Save the human player's individual performance breakdown.
    Extracted from the speaker_scores array based on their role.
    Used by the History API to show personal progress over time.
    """
    perf = UserPerformance(
        id=uuid.uuid4(),
        user_id=user_id,
        session_id=session_id,
        speaker_role=speaker_score_data["speaker_role"],
        total_score=speaker_score_data["total_score"],
        argument_score=speaker_score_data["content_score"],    # content → argument
        rebuttal_score=speaker_score_data["strategy_score"],   # strategy → rebuttal
        structure_score=speaker_score_data["structure_score"],
        delivery_score=speaker_score_data["style_score"],      # style → delivery
        poi_score=speaker_score_data["poi_score"],
        written_feedback=speaker_score_data["coaching_feedback"],
    )
    db.add(perf)
    db.commit()
    return perf


def get_result_by_session(db: Session, session_id: str):
    """Fetch the adjudication result for a completed session."""
    return db.query(AdjudicationResult).filter(
        AdjudicationResult.session_id == session_id
    ).first()


def get_user_history(db: Session, user_id: str, limit: int = 20) -> list:
    """Fetch a user's past performance records, newest first."""
    return (
        db.query(UserPerformance)
        .filter(UserPerformance.user_id == user_id)
        .order_by(UserPerformance.created_at.desc())
        .limit(limit)
        .all()
    )
