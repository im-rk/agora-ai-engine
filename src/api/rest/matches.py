from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from src.core.database import get_db

from src.schemas.debate_schema import MatchStartRequest, MatchStartResponse, CasePrepResponse
from src.services.match_service import start_new_match
from src.repositories import case_prep_repo

router = APIRouter()


@router.post("", response_model=MatchStartResponse)
async def create_match(
    request: MatchStartRequest,
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/matches
    Creates a new match and triggers AI case preparation.
    Returns: match_id (session_id), case_prep_id, and confirmation message.
    """
    result = await start_new_match(db=db, request=request)
    return result


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