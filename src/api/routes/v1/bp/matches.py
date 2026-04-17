"""
British Parliamentary (BP) Match Endpoints.

API Routes for match management:
- POST   /api/v1/bp/matches              → Create new BP match
- GET    /api/v1/bp/matches              → List user's BP matches
- GET    /api/v1/bp/matches/{id}         → Get BP match details
- PATCH  /api/v1/bp/matches/{id}         → Update match status
- DELETE /api/v1/bp/matches/{id}         → Cancel match

All endpoints require authentication (get_current_user dependency).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.api.dependencies import get_current_user
from src.schemas.auth import CurrentUserData
from src.schemas.common import APIResponse, APIStatusCode
from src.schemas.bp.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListResponse,
    UpdateMatchStatusRequest,
    MatchStatus,
)
from src.services.bp.matches import BPMatchService

logger = logging.getLogger(__name__)
router = APIRouter()
match_service = BPMatchService()


# POST /api/v1/bp/matches - Create New Match
@router.post(
    "",
    response_model=APIResponse[MatchResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create new BP match"
)
async def create_match(
    request: CreateMatchRequest,
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new British Parliamentary debate match.
    
    Business Logic:
    1. Create Motion record (debate topic)
    2. Create CasePrep record (user's prepared case)
    3. Create DebateSession record (the match)
    4. Initialize Redis state (8-speaker schedule)
    5. Generate AI case prep
    
    Authentication: Required (JWT token)
    
    Args:
        request (CreateMatchRequest): 
            - motion: Debate motion text (10-500 chars)
            - team: BP team (opening_government, opening_opposition, 
                    closing_government, closing_opposition)
            - role: BP role (prime_minister, member_of_government, etc.)
        
        user (CurrentUserData): Authenticated user creating the match
        db (Session): Database session
    
    Returns:
        APIResponse[MatchResponse]: Created match
    
    Raises:
        HTTPException(401): Unauthorized
        HTTPException(500): Server error
    
    Example Request:
    {
        "motion": "This house believes AI development should be regulated",
        "team": "opening_government",
        "role": "prime_minister"
    }
    
    Example Response:
    {
        "status": "success",
        "message": "Match created successfully",
        "data": {
            "match_id": "match_uuid",
            "motion": "This house believes...",
            "status": "debate_in_progress",
            "created_by": "user_uuid",
            "your_role": "prime_minister",
            "your_team": "opening_government",
            "created_at": "2026-04-17T10:00:00Z",
            "participants": []
        }
    }
    """
    try:
        logger.info(f"Creating BP match for user {user.user_id}: {request.motion[:50]}...")
        
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


# GET /api/v1/bp/matches - List Matches

@router.get(
    "",
    response_model=APIResponse[MatchListResponse],
    summary="List user's BP matches"
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
    """
    Get paginated list of user's BP matches.
    
    Query Features:
    - Filter by match status (pending, in_progress, completed, cancelled)
    - Sort by creation or start time
    - Pagination with configurable page size
    
    Authentication: Required (JWT token)
    
    Query Parameters:
        status (Optional[str]): Filter by status
        skip (int): Pagination offset (default: 0)
        limit (int): Results per page (default: 10, max: 100)
        sort_by (str): Sort field (default: created_at)
        order (str): Sort order (default: desc)
    
    Returns:
        APIResponse[MatchListResponse]: Paginated match list
    
    Raises:
        HTTPException(401): Unauthorized
        HTTPException(500): Server error
    """
    try:
        logger.info(f"Listing BP matches for user {user.user_id}")
        
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


# GET /api/v1/bp/matches/{id} - Get Match Details

@router.get(
    "/{match_id}",
    response_model=APIResponse[MatchResponse],
    summary="Get BP match details"
)
async def get_match(
    match_id: str = Query(..., description="Match UUID"),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific BP match.
    
    Returns full match state including:
    - All 8 participants with roles and speech details
    - 4 teams (OG, OO, CG, CO)
    - Current debate status
    - Next speaker in line
    - Match metadata
    
    Authentication: Required (JWT token)
    
    Path Parameters:
        match_id (str): Match UUID
    
    Returns:
        APIResponse[MatchResponse]: Complete match details
    
    Raises:
        HTTPException(401): Unauthorized
        HTTPException(404): Match not found
        HTTPException(500): Server error
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


# PATCH /api/v1/bp/matches/{id} - Update Match Status

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
        status (MatchStatus): New status
        reason (Optional[str]): Reason for status change
    
    Returns:
        APIResponse[MatchResponse]: Updated match
    
    Raises:
        HTTPException(400): Invalid status transition
        HTTPException(401): Unauthorized
        HTTPException(403): Forbidden (not authorized to modify)
        HTTPException(404): Match not found
        HTTPException(500): Server error
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


# DELETE /api/v1/bp/matches/{id} - Cancel Match

@router.delete(
    "/{match_id}",
    response_model=APIResponse,
    summary="Cancel BP match"
)
async def cancel_match(
    match_id: str,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel/delete a BP match.
    
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
