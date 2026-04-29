"""
Users Router: User-level aggregate statistics.

Provides:
- GET /api/v1/users/stats  → win rate, avg score, best score, wins/losses
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.api.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", summary="Get user aggregate debate statistics")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Aggregate stats across both AP and BP formats for the current user.

    Queries:
    - debate_sessions: total matches, wins, losses by side
    - adjudication_results: avg and best gov/opp scores for the user's sessions

    Returns:
        {
          "total_debates": int,
          "completed_debates": int,
          "wins": int,
          "losses": int,
          "win_rate": float,           # 0–100
          "avg_score": float | None,   # 0–100, null if no completed debates
          "best_score": float | None,  # 0–100, null if no completed debates
        }
    """
    user_id = current_user.user_id

    try:
        # ── 1. Aggregate from debate_sessions ──────────────────────────────
        sessions_query = text("""
            SELECT
                ds.id,
                ds.status,
                ds.human_side,
                ar.winning_team,
                ar.gov_total_score,
                ar.opp_total_score
            FROM debate_sessions ds
            LEFT JOIN adjudication_results ar ON ar.session_id = ds.id
            WHERE ds.user_id = :user_id
        """)

        rows = db.execute(sessions_query, {"user_id": user_id}).fetchall()

        total_debates = len(rows)
        completed_debates = 0
        wins = 0
        losses = 0
        scores: list[float] = []

        for row in rows:
            session_id, status, human_side, winning_team, gov_score, opp_score = row

            is_finished = status in ("FINISHED", "finished", "completed", "COMPLETED")
            if not is_finished:
                continue

            completed_debates += 1

            if winning_team is None:
                continue

            # Determine if the human won
            human_side_lower = (human_side or "").lower()
            winning_team_lower = (winning_team or "").lower()

            # Government side → check if winning_team contains "government"
            if "government" in human_side_lower:
                user_score = gov_score or 0.0
                did_win = "government" in winning_team_lower
            else:
                user_score = opp_score or 0.0
                did_win = "opposition" in winning_team_lower

            if did_win:
                wins += 1
            else:
                losses += 1

            if user_score and user_score > 0:
                scores.append(float(user_score))

        # ── 2. Compute derived metrics ─────────────────────────────────────
        win_rate = round((wins / completed_debates * 100), 1) if completed_debates > 0 else 0.0
        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        best_score = round(max(scores), 1) if scores else None

        return {
            "status": "success",
            "data": {
                "total_debates": total_debates,
                "completed_debates": completed_debates,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_score": avg_score,
                "best_score": best_score,
            }
        }

    except Exception as e:
        logger.error(f"Failed to fetch stats for user {user_id}: {e}")
        return {
            "status": "success",
            "data": {
                "total_debates": 0,
                "completed_debates": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_score": None,
                "best_score": None,
            }
        }
