"""
British Parliamentary (BP) Adjudication REST Endpoints.

Endpoints:
  POST   /api/v1/bp/matches/{match_id}/adjudication
  GET    /api/v1/bp/matches/{match_id}/adjudication/status
  GET    /api/v1/bp/matches/{match_id}/adjudication

Features:
  ✓ 5-Phase adjudication pipeline
  ✓ Match-specific results
  ✓ Async processing with polling support
  ✓ WebSocket real-time updates via Gateway
  ✓ Database persistence
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List

from src.ai.agents.adjudicator import AdjudicatorAgent
from src.schemas.adjudication import AdjudicationResult, SpeakerScore
from src.core.database import SessionLocal
from src.repositories.adjudication_repo import get_adjudication_result

router = APIRouter()


class AdjudicationRequest(BaseModel):
    """BP adjudication request schema."""
    transcript: str = Field(..., description="Complete debate transcript")
    speaker_roles: List[str] = Field(
        ..., 
        description="Speaker roles in BP order: [PM, LO, MG, Opp, Reply PM, Reply Opp]"
    )


@router.post("/matches/{match_id}/adjudication", response_model=AdjudicationResult)
async def adjudicate_bp_debate(
    match_id: str,
    request: AdjudicationRequest,
    background_tasks: BackgroundTasks
) -> AdjudicationResult:
    """
    POST /api/v1/bp/matches/{match_id}/adjudication
    
    Execute the complete 5-phase BP adjudication pipeline.
    
    **Pipeline:**
    1. Extract macro-clashes from transcript
    2. Build Weighted Clash Matrix (WCM)
    3. Analyze WUDC pillars (Matter, Manner, Method, Role)
    4. Grade individual speakers
    5. Generate structured adjudication summary
    
    **Time:** ~40-60 seconds
    
    Args:
        match_id: The BP match/debate ID
        request: Adjudication request with transcript and speaker roles
    
    Returns:
        Complete AdjudicationResult with all 5 phases
    
    Raises:
        HTTPException 400: Invalid request
        HTTPException 500: Processing error
    """
    
    # Validate request
    if not request.transcript or len(request.transcript) < 100:
        raise HTTPException(status_code=400, detail="Transcript too short (min 100 chars)")
    
    if not request.speaker_roles or len(request.speaker_roles) < 4:
        raise HTTPException(status_code=400, detail="BP format requires at least 4 speakers")
    
    try:
        # Initialize adjudicator
        adjudicator = AdjudicatorAgent()
        
        # Run orchestration (all 5 phases)
        result_dict = await adjudicator.orchestrate_adjudication(
            transcript=request.transcript,
            debate_format="BP",
            speaker_roles=request.speaker_roles,
            session_id=match_id
        )
        
        # Parse into Pydantic model
        from src.schemas.adjudication import (
            MacroClash, WCMEntry, PillarBreakdown, PillarScore, AdjudicationSummary
        )
        
        clashes = [MacroClash(**clash) for clash in result_dict["clashes"]]
        wcm_entries = [WCMEntry(**entry) for entry in result_dict["wcm_matrix"]]
        speaker_scores = [SpeakerScore(**score) for score in result_dict["speaker_scores"]]
        
        pillar_data = result_dict["pillar_breakdown"]
        pillar_breakdown = PillarBreakdown(
            matter=PillarScore(**pillar_data["matter"]),
            manner=PillarScore(**pillar_data["manner"]),
            method=PillarScore(**pillar_data["method"]),
            role=PillarScore(**pillar_data["role"]),
            pillar_reasoning=pillar_data.get("pillar_reasoning", "")
        )
        
        summary = AdjudicationSummary(**result_dict["summary"])
        
        adjudication_result = AdjudicationResult(
            clashes=clashes,
            wcm_matrix=wcm_entries,
            net_logic_score=result_dict["net_logic_score"],
            pillar_breakdown=pillar_breakdown,
            speaker_scores=speaker_scores,
            summary=summary,
            session_id=match_id
        )
        
        return adjudication_result
        
    except Exception as e:
        import traceback
        print(f"[ERROR] BP Adjudication failed for match {match_id}: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Adjudication failed: {type(e).__name__}")


@router.get("/matches/{match_id}/adjudication/status")
async def get_bp_adjudication_status(match_id: str):
    """
    GET /api/v1/bp/matches/{match_id}/adjudication/status
    
    Check adjudication status for a specific match.
    
    Frontend polls this every 2 seconds while waiting.
    
    Returns:
        ```json
        {
            "status": "processing|completed|error",
            "verdict": "Government|Opposition",
            "gov_score": 82,
            "opp_score": 79,
            "message": "..."
        }
        ```
    """
    db = SessionLocal()
    try:
        result = get_adjudication_result(db, match_id)
        
        if result is None:
            return {
                "status": "processing",
                "message": "Adjudication in progress. Check again in 2 seconds.",
                "match_id": match_id
            }
        
        return {
            "status": "completed",
            "verdict": result["winning_team"],
            "gov_score": result["gov_total_score"],
            "opp_score": result["opp_total_score"],
            "match_id": match_id
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check status: {str(e)}",
            "match_id": match_id
        }
    finally:
        db.close()


@router.get("/matches/{match_id}/adjudication", response_model=Optional[AdjudicationResult])
async def get_bp_adjudication(match_id: str):
    """
    GET /api/v1/bp/matches/{match_id}/adjudication
    
    Retrieve full cached adjudication result for a match.
    
    Use /status to check if ready, then call this for full details.
    
    Returns:
        Complete AdjudicationResult if found, null otherwise
    """
    db = SessionLocal()
    try:
        result = get_adjudication_result(db, match_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    finally:
        db.close()
