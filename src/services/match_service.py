"""
Match Service: Orchestrates match lifecycle (setup, prep, execution, adjudication).

This service layer bridges FastAPI routers and lower-level repositories,
enforcing the DDD boundary: Router → Service → Repository/AI.
"""

import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.schemas.debate_schema import MatchStartRequest
from src.services.case_prep_service import prepare_case
from src.repositories import debate_repo
from src.repositories import case_prep_repo
from src.models.user import SkillLevel, User
from src.models.setup import Motion, MotionCategory


def map_format(format_str: str) -> str:
    """Maps user-friendly format strings to standardized codes (BP/AP)."""
    format_map = {
        "Asian Parliamentary": "AP",
        "British Parliamentary": "BP",
        "AP": "AP",
        "BP": "BP"
    }

    if format_str not in format_map:
        raise HTTPException(status_code=400, detail="Invalid debate format")

    return format_map[format_str]


async def start_new_match(db: Session, request: MatchStartRequest) -> dict:
    """Initiates new debate match with AI case preparation."""
    try:
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        motion = Motion(
            id=uuid.uuid4(),
            motion_text=request.motion_text,
            category=MotionCategory.CUSTOM,
            is_custom=True
        )
        db.add(motion)
        db.flush()

        new_session = debate_repo.create_debate_session(
            db=db,
            user_id=user.id,
            motion_id=str(motion.id),
            format_type=map_format(request.format),
            side=request.side,
            skill_level=user.skill_level
        )

        new_prep = case_prep_repo.create_case_prep(
            db=db,
            user_id=user.id,
            motion_id=str(motion.id),
            side=request.side
        )

        db.commit()
        db.refresh(new_session)
        db.refresh(new_prep)

        await prepare_case(
            db=db,
            user_id=str(user.id),
            motion_id=str(motion.id),
            session_id=str(new_session.id),
            case_prep_id=str(new_prep.id),
            motion_text=request.motion_text,
            side=request.side,
            format=map_format(request.format)
        )

        return {
            "session_id": str(new_session.id),
            "case_prep_id": str(new_prep.id),
            "message": "Match created successfully! AI case prep ready."
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")