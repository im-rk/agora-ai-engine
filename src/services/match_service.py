"""
Match Service: Orchestrates match lifecycle (setup, prep, execution, adjudication).

This service layer bridges FastAPI routers and lower-level repositories,
enforcing the DDD boundary: Router → Service → Repository/AI.
"""

import uuid
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.schemas.debate_schema import MatchStartRequest
from src.services.case_prep_service import prepare_case
from src.repositories import debate_repo
from src.repositories import case_prep_repo
from src.models.user import SkillLevel, User
from src.models.setup import Motion, MotionCategory
from src.engine.state import state_manager


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
        # Convert string user_id to UUID for database query
        user_uuid = UUID(request.user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
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

        await state_manager.initialize_match(
            match_id=str(new_session.id),
            human_side=request.side,
            format_type=request.format,
            preferred_role=request.preferred_role
        )

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
        print(f"🔴 ERROR in start_new_match: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")