from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.repositories.results_repo import get_result_by_session, get_user_history

router = APIRouter()

@router.get("/{session_id}/results")
def get_debate_results(
    session_id: str = Path(..., description="The debate session ID"),
    db: Session = Depends(get_db),
):
    result = get_result_by_session(db=db, session_id=session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not available yet.")

    return {
        "session_id": str(result.session_id),
        "winning_team": result.winning_team,
        "gov_total_score": result.gov_total_score,
        "opp_total_score": result.opp_total_score,
        "clash_table": result.clash_table,
        "speaker_scores": result.speaker_scores,
        "created_at": result.created_at.isoformat(),
    }

@router.get("/history")
def get_user_debate_history(
    user_id: str = Query(...), limit: int = Query(20), db: Session = Depends(get_db)
):
    records = get_user_history(db=db, user_id=user_id, limit=limit)
    return {
        "debates": [{
            "session_id": str(r.session_id), "speaker_role": r.speaker_role,
            "total_score": r.total_score, "created_at": r.created_at.isoformat(),
        } for r in records]
    }
