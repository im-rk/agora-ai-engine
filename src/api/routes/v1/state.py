"""
Match State Endpoint - For Frontend Rejoin Protocol

When user disconnects and reconnects, they fetch full match state
to reconstruct UI and determine what audio needs TTS synthesis.

Endpoint:
- GET /api/v1/matches/{match_id}/state - Get full match state for rejoin
"""

import logging
from fastapi import APIRouter, HTTPException, Path, status
from src.engine.state import state_manager
from src.schemas.common import APIResponse, APIStatusCode

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/matches/{match_id}/state",
    response_model=APIResponse,
    summary="Get current match state for rejoin protocol",
    tags=["Match State"],
)
async def get_match_state(
    match_id: str = Path(..., description="Match ID"),
):
    """
    Get full match state for rejoin protocol.
    
    Called by frontend when user reconnects after WebSocket disconnect.
    Returns all state needed to:
    1. Reconstruct match UI (speakers, transcript, current turn)
    2. Resume timer from correct position (accounting for offline time)
    3. Get cached AI speech for TTS synthesis
    
    Response includes:
    - active_stream_buffer: Cached AI speech (for TTS)
    - match_started_at: When match began (Unix timestamp)
    - total_offline_duration: Accumulated offline time (seconds)
    - current_turn_index: Current speaker index
    - schedule: All speakers in order
    - is_user_connected: Connection status
    - ai_stream_status: AI generation state (IDLE, STREAMING, PAUSED, COMPLETED)
    - time_remaining_seconds: Calculated remaining time (excluding offline time)
    
    Frontend uses this to:
    1. Reconstruct match UI from schedule
    2. Resume timer from correct position
    3. Get cached speech for TTS synthesis via Gateway
    
    Example Response:
    ```json
    {
        "status": "success",
        "data": {
            "match_id": "match-abc-123",
            "format_type": "AP",
            "status": "IN_PROGRESS",
            "current_turn_index": 1,
            "schedule": [
                {
                    "role": "Prime Minister",
                    "side": "Government",
                    "player_type": "ai"
                },
                ...
            ],
            "match_started_at": 1715340000,
            "match_duration_seconds": 1800,
            "current_turn_duration_seconds": 300,
            "total_offline_duration": 145,
            "time_remaining_seconds": 155,
            "is_user_connected": true,
            "ai_stream_status": "COMPLETED",
            "active_stream_buffer": "The economy is crucial for...",
            "transcript": [...]
        }
    }
    ```
    """
    try:
        state = await state_manager.get_state(match_id)
        
        if not state:
            logger.warning(f"Match not found: {match_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match {match_id} not found",
            )
        
        # Return full state so frontend can rejoin
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message="Match state retrieved",
            data={
                "match_id": state.match_id,
                "format_type": state.format_type,
                "status": state.status,
                "current_turn_index": state.current_turn_index,
                "schedule": [s.model_dump() for s in state.schedule],
                "match_started_at": state.match_started_at,
                "match_duration_seconds": state.match_duration_seconds,
                "current_turn_duration_seconds": state.current_turn_duration_seconds,
                "total_offline_duration": state.total_offline_duration,
                "time_remaining_seconds": state.time_remaining_seconds,
                "is_user_connected": state.is_user_connected,
                "ai_stream_status": state.ai_stream_status,
                "active_stream_buffer": state.active_stream_buffer,  # For TTS
                "transcript": state.transcript,
            },
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching match state for {match_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve match state",
        )
