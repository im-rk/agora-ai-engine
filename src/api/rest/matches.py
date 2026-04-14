# File: src/api/rest/matches.py
# RESTful API following enterprise design patterns
# Parent Resource: Match (DebateSession)
# All endpoints revolve around /api/v1/matches/{match_id}

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.core.database import get_db

from src.schemas.debate_schema import MatchStartRequest, MatchStartResponse, CasePrepResponse
from src.services.match_service import start_new_match
from src.repositories import case_prep_repo
from src.ai.agents.debater import DebaterAgent
from src.api.dependencies import get_current_user_id

router = APIRouter()


class DebaterResponseRequest(BaseModel):
    """Request for generating a live debate response."""
    transcript: str
    speaker_role: str  # "affirmative" or "negative"
    speaker_id: str  # Unique speaker identifier
    personality_trait: str = "balanced"  # Optional persona


class DebaterResponseMessage(BaseModel):
    """Response message from debater agent."""
    status: str = "streaming"
    message: str = "Response tokens are being published to Redis in real-time"
    redis_channel: str




@router.get("/{match_id}/prep", response_model=CasePrepResponse)
def fetch_prep_by_match(
    match_id: str = Path(..., description="The match/session ID"),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/matches/{match_id}/prep
    Retrieves the case preparation for a specific match.
    Frontend use: Load prep data in the "Case Prep Room" UI.
    """
    prep = case_prep_repo.get_case_prep_by_match(db=db, match_id=match_id)

    if not prep:
        raise HTTPException(
            status_code=404,
            detail="Case prep not found for this match"
        )

    return CasePrepResponse(
        id=str(prep.id),
        side=prep.side,
        arguments=prep.arguments or [],
        counter_arguments=prep.counter_arguments or [],
        evidence=prep.evidence or []
    )


@router.post("/{match_id}/response", response_model=DebaterResponseMessage)
async def generate_live_response(
    match_id: str = Path(..., description="The match/session ID"),
    request: DebaterResponseRequest = None
):
    """
    POST /api/v1/matches/{match_id}/response
    
    Generate a live debate response using 4-phase FAANG pipeline:
    1. State Tracking: Parse transcript into clash matrix
    2. Query Synthesis: Generate targeted search queries
    3. Retrieve & Re-Rank: Find top 3 evidence pieces
    4. Generation: Stream response via Redis
    
    Response tokens are published to Redis channel in real-time.
    Frontend subscribes to Redis channel and displays tokens as they arrive.
    
    Args:
        match_id: Match/session ID
        request: DebaterResponseRequest with transcript, role, speaker_id
    
    Returns:
        Confirmation that streaming has started + Redis channel name
    """
    try:
        # Initialize debater agent
        debater = DebaterAgent()
        
        # Launch 4-phase orchestration (async, non-blocking)
        # Tokens stream to Redis in background
        await debater.orchestrate_debater_response(
            transcript=request.transcript,
            speaker_role=request.speaker_role,
            speaker_id=request.speaker_id,
            personality_trait=request.personality_trait
        )
        
        # Return confirmation (response already streaming to Redis)
        redis_channel = f"debate:{request.speaker_id}:response"
        
        return DebaterResponseMessage(
            status="streaming",
            message="Response is being generated and streamed to Redis channel",
            redis_channel=redis_channel
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating debate response: {str(e)}"
        )
    
@router.post("", response_model=MatchStartResponse)
async def create_match(
    request: MatchStartRequest,
    user_id: str = Depends(get_current_user_id), # Extract user from the token!
    db: Session = Depends(get_db)
):
    # Pass user_id down to the service
    result = await start_new_match(db=db, request=request, user_id=user_id)
    return result