# File: src/api/rest/matches.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db

from src.schemas.debate_schema import MatchStartRequest, MatchStartResponse
from src.services.match_service import start_new_match
from src.repositories import case_prep_repo

router = APIRouter()


@router.post("/start", response_model=MatchStartResponse)
async def create_match_endpoint(
    request: MatchStartRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint to start a new debate match and generate AI case prep.
    """

    result = await start_new_match(db=db, request=request)
    return result


@router.get("/case-prep/{prep_id}")
def fetch_case_prep(prep_id: str, db: Session = Depends(get_db)):
    """
    Retrieves a previously generated case preparation.
    """
    prep = case_prep_repo.get_case_prep_by_id(db=db, prep_id=prep_id)

    if not prep:
        raise HTTPException(status_code=404, detail="Case Prep not found")

    return prep