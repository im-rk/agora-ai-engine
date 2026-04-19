"""
Adjudication REST Endpoint: 5-Phase Pipeline API.

POST /api/adjudicate
  Request: { transcript, debate_format, speaker_roles, session_id }
  Response: Complete AdjudicationResult (all 5 phases + JSON structure)

GET /api/adjudications/{session_id}
  Response: Cached adjudication result

Features:
  ✓ Async pipeline processing
  ✓ Progress logging (for long LLM calls)
  ✓ Error handling with detailed messages
  ✓ Database persistence
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from src.ai.agents.adjudicator import AdjudicatorAgent
from src.schemas.adjudication import AdjudicationResult, SpeakerScore
from src.core.database import SessionLocal
from src.repositories.ap.debates import get_adjudication_result

router = APIRouter(prefix="/api/adjudications", tags=["adjudications"])


class AdjudicationRequest(BaseModel):
    """Request schema for adjudication endpoint."""
    transcript: str = Field(..., description="Complete debate transcript")
    debate_format: str = Field(..., description="Format (AP, BP, etc.)")
    speaker_roles: List[str] = Field(..., description="Speaker roles in order")
    session_id: Optional[str] = Field(None, description="Debate session ID")


class AdjudicationStatus(BaseModel):
    """Status response for long-running adjudication."""
    status: str = Field(..., description="processing, completed, failed")
    progress: Optional[str] = Field(None, description="Current phase")
    result: Optional[AdjudicationResult] = None
    error: Optional[str] = None


@router.post("/", response_model=AdjudicationResult)
async def adjudicate_debate(
    request: AdjudicationRequest,
    background_tasks: BackgroundTasks
) -> AdjudicationResult:
    """
    POST /api/adjudications
    
    Execute the complete 5-phase adjudication pipeline.
    
    **Pipeline:**
    1. Extract macro-clashes from transcript
    2. Build Weighted Clash Matrix (WCM)
    3. Analyze WUDC pillars (Matter, Manner, Method, Role)
    4. Grade individual speakers
    5. Generate structured adjudication summary
    
    **Request:**
    ```json
    {
      "transcript": "Gov PM: ...\nOpp LO: ...\n",
      "debate_format": "AP",
      "speaker_roles": ["Gov PM", "Gov MG", "Opp LO", "Opp MG", "Gov Reply", "Opp Reply"],
      "session_id": "debate-123"
    }
    ```
    
    **Response:**
    ```json
    {
      "clashes": [...],
      "wcm_matrix": [...],
      "net_logic_score": 5.0,
      "pillar_breakdown": {...},
      "speaker_scores": [...],
      "summary": {...},
      "winning_team": "Government",
      "gov_total_score": 72,
      "opp_total_score": 60,
      "created_at": "2024-01-15T10:30:00",
      "session_id": "debate-123"
    }
    ```
    
    **Time:** ~30-60 seconds (3 LLM calls)
    
    Raises:
        HTTPException 400: Invalid request format
        HTTPException 500: LLM processing error
    """
    
    # Validate request
    if not request.transcript or len(request.transcript) < 100:
        raise HTTPException(status_code=400, detail="Transcript too short (min 100 chars)")
    
    if not request.speaker_roles or len(request.speaker_roles) < 4:
        raise HTTPException(status_code=400, detail="Need at least 4 speakers")
    
    try:
        # Initialize adjudicator
        adjudicator = AdjudicatorAgent()
        
        # Run orchestration (all 5 phases)
        result_dict = await adjudicator.orchestrate_adjudication(
            transcript=request.transcript,
            debate_format=request.debate_format,
            speaker_roles=request.speaker_roles,
            session_id=request.session_id
        )
        
        # Parse into Pydantic model
        # Note: Convert clash/wcm dicts back to objects for schema validation
        from src.schemas.adjudication import (
            MacroClash, WCMEntry, PillarBreakdown, PillarScore
        )
        
        clashes = [
            MacroClash(**clash) for clash in result_dict["clashes"]
        ]
        
        wcm_entries = [
            WCMEntry(**entry) for entry in result_dict["wcm_matrix"]
        ]
        
        speaker_scores = [
            SpeakerScore(**score) for score in result_dict["speaker_scores"]
        ]
        
        pillar_data = result_dict["pillar_breakdown"]
        pillar_breakdown = PillarBreakdown(
            matter=PillarScore(**pillar_data["matter"]),
            manner=PillarScore(**pillar_data["manner"]),
            method=PillarScore(**pillar_data["method"]),
            role=PillarScore(**pillar_data["role"]),
            pillar_reasoning=pillar_data.get("pillar_reasoning", "")
        )
        
        from src.schemas.adjudication import AdjudicationSummary
        summary = AdjudicationSummary(
            **result_dict["summary"]
        )
        
        adjudication_result = AdjudicationResult(
            clashes=clashes,
            wcm_matrix=wcm_entries,
            net_logic_score=result_dict["net_logic_score"],
            pillar_breakdown=pillar_breakdown,
            speaker_scores=speaker_scores,
            summary=summary,
            session_id=request.session_id
        )
        
        return adjudication_result
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Adjudication failed: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Adjudication failed: {type(e).__name__}"
        )


@router.get("/{session_id}/status")
async def get_adjudication_status(session_id: str):
    """
    GET /api/adjudications/{session_id}/status
    
    Check adjudication status and progress.
    
    Frontend polls this endpoint every 2 seconds while waiting for adjudication.
    
    Returns:
        {
            "status": "processing" | "completed" | "error",
            "verdict": "Government" | "Opposition" (if completed),
            "gov_score": 82 (if completed),
            "opp_score": 79 (if completed),
            "message": "Adjudication in progress..."
        }
    """
    db = SessionLocal()
    try:
        result = get_adjudication_result(db, session_id)
        
        if result is None:
            # Still processing or not found
            return {
                "status": "processing",
                "message": "Adjudication in progress. Check again in 2 seconds.",
                "session_id": session_id
            }
        
        # Adjudication complete!
        return {
            "status": "completed",
            "verdict": result["winning_team"],
            "gov_score": result["gov_total_score"],
            "opp_score": result["opp_total_score"],
            "session_id": session_id
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check status: {str(e)}",
            "session_id": session_id
        }
    finally:
        db.close()


@router.get("/{session_id}", response_model=Optional[AdjudicationResult])
async def get_adjudication(session_id: str):
    """
    GET /api/adjudications/{session_id}
    
    Retrieve full cached adjudication result for a debate session.
    
    Use /status endpoint to check if ready, then call this to get full details.
    
    Returns:
        Complete AdjudicationResult if found, null otherwise
    """
    db = SessionLocal()
    try:
        result = get_adjudication_result(db, session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    finally:
        db.close()
