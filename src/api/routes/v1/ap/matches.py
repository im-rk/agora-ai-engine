"""
Asian Parliamentary (AP) Match Endpoints.

API Routes for match management:
- POST   /api/v1/ap/matches              → Create new AP match
- GET    /api/v1/ap/matches              → List user's AP matches
- GET    /api/v1/ap/matches/{id}         → Get AP match details
- PATCH  /api/v1/ap/matches/{id}         → Update match status
- DELETE /api/v1/ap/matches/{id}         → Cancel match

All endpoints require authentication (get_current_user dependency).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.api.dependencies import get_current_user
from src.schemas.auth import CurrentUserData
from src.schemas.common import APIResponse, APIStatusCode
from src.schemas.ap.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListResponse,
    UpdateMatchStatusRequest,
    MatchStatus,
)
from src.services.ap.matches import APMatchService

logger = logging.getLogger(__name__)
router = APIRouter()
match_service = APMatchService()

# ...

# POST /api/v1/ap/matches - Create New Match
@router.post(
    "",
    response_model=APIResponse[MatchResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create new AP match"
)
async def create_match(
    request: CreateMatchRequest,
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new Asian Parliamentary debate match.
    """
    try:
        logger.info(f"Creating AP match for user {user.user_id}: {request.motion[:50]}...")
        
        # Create match via service
        match = await match_service.create_match(db, user.user_id, request)
        
        logger.info(f"Match created: {match.match_id}")
        
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message="Match created successfully",
            data=match
        )
    
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create match: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create match"
        )


# GET /api/v1/ap/matches - List Matches

@router.get(
    "",
    response_model=APIResponse[MatchListResponse],
    summary="List user's AP matches"
)
async def list_matches(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: pending, in_progress, completed, cancelled"
    ),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, started_at"
    ),
    order: str = Query(
        "desc",
        description="Sort order: asc, desc"
    ),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"Listing AP matches for user {user.user_id}")
        
        matches = await match_service.list_matches(
            db=db,
            user_id=user.user_id,
            status=status_filter,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            order=order
        )
        
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message=f"Found {matches['total']} total matches, showing {len(matches['matches'])} results",
            data={
                "matches": matches["matches"],
                "total": matches["total"],
                "skip": matches["skip"],
                "limit": matches["limit"]
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to list matches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve matches"
        )


# GET /api/v1/ap/matches/{id} - Get Match Details

@router.get(
    "/{match_id}",
    response_model=APIResponse[MatchResponse],
    summary="Get AP match details"
)
async def get_match(
    match_id: str = Path(..., description="Match UUID"),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific AP match.
    
    Returns full match state including:
    - All 6 participants with roles and speech details
    - Government and opposition teams
    - Current debate status
    - Next speaker in line
    - Match metadata (tournament, judge, etc.)
    
    Authentication: Required (JWT token)
    
    Path Parameters:
        match_id (str): Match UUID
    
    Returns:
        APIResponse[MatchResponse]: Complete match details
    
    Raises:
        HTTPException(401): Unauthorized
        HTTPException(404): Match not found
        HTTPException(500): Server error
    
    Example Response:
    {
        "status": "success",
        "data": {
            "id": "match_uuid",
            "title": "...",
            "format": "asian_parliamentary",
            "status": "in_progress",
            "government": { ... 3 speakers ... },
            "opposition": { ... 3 speakers ... },
            "speeches_completed": 3,
            "current_speaker_index": 2,
            "next_speaker": {
                "role": "second_speaker",
                "side": "opposition",
                "user_id": "user_5",
                "order_position": 4
            },
            ...
        }
    }
    """
    try:
        logger.info(f"Retrieving match {match_id} for user {user.user_id}")
        
        match = await match_service.get_match(db, match_id)
        
        if not match:
            logger.warning(f"Match not found: {match_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found"
            )
        
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            data=match
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve match: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve match"
        )


# PATCH /api/v1/ap/matches/{id} - Update Match Status

@router.patch(
    "/{match_id}",
    response_model=APIResponse[MatchResponse],
    summary="Update match status"
)
async def update_match_status(
    match_id: str,
    request: UpdateMatchStatusRequest,
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update match status with state validation.
    
    Status Transitions:
    - pending → in_progress: When first speech is recorded
    - pending → cancelled: Can cancel anytime
    - in_progress → completed: When judging is submitted
    - in_progress → cancelled: Can cancel anytime
    - completed/cancelled: Terminal states (no further transitions)
    
    Authentication: Required (JWT token)
    Only match creator or adjudicator can update status.
    
    Path Parameters:
        match_id (str): Match UUID
    
    Request Body:
        status (MatchStatus): New status (pending, in_progress, completed, cancelled)
        reason (Optional[str]): Reason for status change (required for cancellation)
    
    Returns:
        APIResponse[MatchResponse]: Updated match
    
    Raises:
        HTTPException(400): Invalid status transition
        HTTPException(401): Unauthorized
        HTTPException(403): Forbidden (not authorized to modify)
        HTTPException(404): Match not found
        HTTPException(500): Server error
    
    Example Request (Complete a match):
    {
        "status": "completed",
        "reason": "Judging submitted successfully"
    }
    
    Example Request (Cancel a match):
    {
        "status": "cancelled",
        "reason": "Technical difficulties - will reschedule"
    }
    """
    try:
        logger.info(f"Updating match {match_id} status to {request.status}")
        
        # TODO: Add authorization check - only creator or adjudicator can update
        
        match = await match_service.update_match_status(
            db,
            match_id,
            request.status,
            request.reason
        )
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found"
            )
        
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message=f"Match status updated to {request.status}",
            data=match
        )
    
    except ValueError as e:
        logger.warning(f"Invalid status transition: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update match status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update match status"
        )


# DELETE /api/v1/ap/matches/{id} - Cancel Match

@router.delete(
    "/{match_id}",
    response_model=APIResponse,
    summary="Cancel AP match"
)
async def cancel_match(
    match_id: str,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel/delete an AP match.
    
    Soft Delete Behavior:
    - Doesn't actually delete match from database
    - Sets status to "cancelled"
    - Preserves match history for records/statistics
    - Can be cancelled at any stage (pending, in_progress)
    
    Authentication: Required (JWT token)
    Only match creator can cancel.
    
    Path Parameters:
        match_id (str): Match UUID
    
    Query Parameters:
        reason (Optional[str]): Reason for cancellation
    
    Returns:
        APIResponse: Success/failure message
    
    Raises:
        HTTPException(401): Unauthorized
        HTTPException(403): Forbidden (not creator)
        HTTPException(404): Match not found
        HTTPException(500): Server error
    
    Example Response:
    {
        "status": "success",
        "message": "Match cancelled successfully",
        "data": null
    }
    """
    try:
        logger.info(f"Cancelling match {match_id} by user {user.user_id}")
        
        # TODO: Add authorization check - only creator can cancel
        
        success = await match_service.cancel_match(db, match_id, reason)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found"
            )
        
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message=f"Match cancelled successfully. Reason: {reason or 'Not specified'}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel match: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel match"
        )
