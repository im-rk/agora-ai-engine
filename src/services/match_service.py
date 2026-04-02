from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.schemas.setup_schema import MatchStartRequest
from src.ai.agents.prep_coach import generate_case_prep
from src.repositories import debate_repo

async def start_new_match(db: Session, request: MatchStartRequest):
    print(f" Service: Starting new match for '{request.motion_text}'")
    
    try:
        # 1. Use the Repository to stage the DB inserts
        new_session = debate_repo.create_debate_session(
            db=db, 
            user_id=request.user_id, 
            format_type=request.format, 
            side=request.side
        )
        
        new_prep = debate_repo.create_case_prep(
            db=db, 
            user_id=request.user_id, 
            side=request.side
        )

        # 2. Commit the transaction ONLY ONCE at the Service level
        db.commit() 
        db.refresh(new_session)
        db.refresh(new_prep)

        # 3. Call the AI Agent (The Chef)
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