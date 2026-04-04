from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid

from src.schemas.debate_schema import MatchStartRequest
from src.ai.agents.prep_coach import generate_case_prep
from src.repositories import debate_repo
from src.models.user import SkillLevel, User
from src.models.setup import Motion, MotionCategory


# --------------------------------------
# FORMAT MAPPER
# --------------------------------------
def map_format(format_str: str):
    format_map = {
        "Asian Parliamentary": "AP",
        "British Parliamentary": "BP",
        "AP": "AP",
        "BP": "BP"
    }

    if format_str not in format_map:
        raise HTTPException(status_code=400, detail="Invalid debate format")

    return format_map[format_str]


def start_new_match(db: Session, request: MatchStartRequest):
    print(f" Service: Starting new match for '{request.motion_text}'")

    try:
        # ----------------------------
        # 1️ Validate User
        # ----------------------------
        user = db.query(User).filter(User.id == request.user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        skill_level = user.skill_level

        # ----------------------------
        # 2️ Create Motion
        # ----------------------------
        motion = Motion(
            id=uuid.uuid4(),
            motion_text=request.motion_text,
            category=MotionCategory.CUSTOM,
            is_custom=True
        )

        db.add(motion)
        db.flush()

        #  DEBUG (important)
        print("FORMAT BEFORE:", request.format)
        print("FORMAT AFTER:", map_format(request.format))

        # ----------------------------
        # 3️ Create Debate Session
        # ----------------------------
        new_session = debate_repo.create_debate_session(
            db=db,
            user_id=user.id,
            motion_id=str(motion.id),
            format_type=map_format(request.format),  #  FIXED HERE
            side=request.side,
            skill_level=skill_level
        )

        # ----------------------------
        # 4️ Create Case Prep
        # ----------------------------
        new_prep = debate_repo.create_case_prep(
            db=db,
            user_id=user.id,
            motion_id=str(motion.id),
            side=request.side
        )

        # ----------------------------
        # 5️ Commit DB Changes
        # ----------------------------
        db.commit()
        db.refresh(new_session)
        db.refresh(new_prep)

        # ----------------------------
        # 6️ Run Prep Coach
        # ----------------------------
        success = generate_case_prep(
            db=db,
            case_prep_id=str(new_prep.id),
            motion_text=request.motion_text,
            side=request.side
        )

        if not success:
            raise HTTPException(status_code=500, detail="AI Prep failed")

        print(" Match + AI Prep completed")

        # ----------------------------
        # 7️ Return Response
        # ----------------------------
        return {
            "session_id": str(new_session.id),
            "case_prep_id": str(new_prep.id),
            "message": "Match created successfully!"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        print(f" Error starting match: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# --------------------------------------
# FETCH CASE PREP
# --------------------------------------
def fetch_case_prep(db: Session, prep_id: str):
    print(f" Service: Fetching case prep {prep_id}")

    prep = debate_repo.get_case_prep_by_id(db=db, prep_id=prep_id)

    if not prep:
        raise HTTPException(status_code=404, detail="Case Prep not found")

    return prep