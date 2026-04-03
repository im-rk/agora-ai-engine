from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.schemas.debate_schema import MatchStartRequest
from src.ai.agents.prep_coach import generate_case_prep
from src.repositories import debate_repo
from src.models.user import SkillLevel
from src.models.setup import Motion, MotionCategory
import uuid

async def start_new_match(db: Session, request: MatchStartRequest):
    print(f" Service: Starting new match for '{request.motion_text}'")
    
    try:
        # 1. Create or get the motion
        motion = Motion(
            id=uuid.uuid4(),
            motion_text=request.motion_text,
            category=MotionCategory.CUSTOM,
            is_custom=True
        )
        db.add(motion)
        db.flush()
        
        # 2. Get user's skill level (for now, defaulting to BEGINNER)
        # TODO: Fetch from user record
        skill_level = SkillLevel.BEGINNER
        
        # 3. Use the Repository to stage the DB inserts
        new_session = debate_repo.create_debate_session(
            db=db,
            user_id=request.user_id,
            motion_id=str(motion.id),
            format_type=request.format,
            side=request.side,
            skill_level=skill_level
        )
        
        new_prep = debate_repo.create_case_prep(
            db=db,
            user_id=request.user_id,
            motion_id=str(motion.id),
            side=request.side
        )

        # 4. Commit the transaction ONLY ONCE at the Service level
        db.commit() 
        db.refresh(new_session)
        db.refresh(new_prep)

        # 5. Call the AI Agent (The Chef)
        success = await generate_case_prep(
            db=db,
            case_prep_id=str(new_prep.id),
            motion_text=request.motion_text,
            side=request.side
        )

        if not success:
            raise HTTPException(status_code=500, detail="AI Agent failed to cook the prep.")

        return {
            "session_id": str(new_session.id),
            "case_prep_id": str(new_prep.id),
            "message": "Match created successfully!"
        }

    except Exception as e:
        db.rollback() 
        print(f"Error starting match: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def fetch_case_prep(db: Session, prep_id: str):
    print(f"Service: Fetching case prep {prep_id} for frontend...")
    
    prep = debate_repo.get_case_prep_by_id(db=db, prep_id=prep_id)
    
    if not prep:
        raise HTTPException(status_code=404, detail="Case Prep not found in database.")
        
    return prep