# File: src/api/rest/matches.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.database import get_db

from src.schemas.debate_schema import MatchStartRequest, MatchStartResponse
from src.services.match_service import start_new_match

router = APIRouter()


@router.post("/start", response_model=MatchStartResponse)
def create_match_endpoint(
    request: MatchStartRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint to start a new debate match and generate AI case prep.
    """

    result = start_new_match(db=db, request=request)
    return result