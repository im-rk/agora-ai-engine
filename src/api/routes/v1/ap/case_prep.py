"""
Asian Parliamentary (AP) Case Prep Endpoints.

API Routes for case preparation:
- POST /api/v1/ap/matches/{match_id}/case-prep → Generate case prep
- GET  /api/v1/ap/matches/{match_id}/case-prep → Get case prep
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.api.dependencies import get_current_user
from src.schemas.auth import CurrentUserData
from src.schemas.ap.case_prep import (
    GenerateCasePrepRequest,
    CasePrepResponse,
)
from src.services.ap.case_prep import APCasePrepService

logger = logging.getLogger(__name__)
router = APIRouter()
case_prep_service = APCasePrepService()


# POST /api/v1/ap/matches/{match_id}/case-prep - Generate Case Prep
@router.post(
    "",
    response_model=CasePrepResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate role-specific case prep"
)
async def generate_case_prep(
    match_id: str,
    request: GenerateCasePrepRequest,
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CasePrepResponse:
    """Generate case prep for user's specific role in match."""
    try:
        logger.info(f"Generating case prep for user {user.user_id} in match {match_id}")
        
        case_prep = await case_prep_service.generate_case_prep(
            db=db,
            user_id=user.user_id,
            match_id=match_id,
            request=request
        )
        
        logger.info(f"Case prep generated: {case_prep.id}")
        return case_prep
    
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate case prep: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate case prep")

# ============================================================================
# GET /api/v1/ap/matches/{match_id}/case-prep - Get Case Prep
# ============================================================================

@router.get(
    "",
    response_model=CasePrepResponse,
    summary="Get case prep for user's role in match"
)
async def get_case_prep(
    match_id: str,
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CasePrepResponse:
    """Get existing case prep for user's role in match."""
    try:
        logger.info(f"Retrieving case prep for user {user.user_id} in match {match_id}")
        
        case_prep = await case_prep_service.get_case_prep(
            db=db,
            user_id=user.user_id,
            match_id=match_id
        )
        
        if not case_prep:
            logger.warning(f"No case prep found for user {user.user_id} in match {match_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case prep not found. Generate one first using POST."
            )
        
        return case_prep
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve case prep: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve case prep"
        )
