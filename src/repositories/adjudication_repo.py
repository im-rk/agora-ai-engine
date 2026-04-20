"""
Adjudication Repository: Database persistence for adjudication results.

Handles:
- Storing complete adjudication results (WCM, pillars, scores)
- Retrieving cached results
- Updating debate records with verdict
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict
import json


def store_adjudication_result(
    db: Session,
    session_id: str,
    adjudication_dict: Dict
) -> bool:
    """
    Store adjudication result in database.
    
    Updates debates table with:
    - verdict (winning team)
    - gov_score, opp_score
    - clash_table (complete WCM + pillars + summary)
    - speaker_scores (individual grades)
    
    Args:
        db: Database session
        session_id: Debate session ID
        adjudication_dict: Complete adjudication result dict
        
    Returns:
        True if successful
    """
    try:
        verdict = adjudication_dict["winning_team"]
        gov_score = adjudication_dict["gov_total_score"]
        opp_score = adjudication_dict["opp_total_score"]
        
        clash_table = adjudication_dict["clash_table"]
        speaker_scores = adjudication_dict["speaker_scores"]
        
        # Update adjudication_results table (Supabase PostgreSQL)
        query = text("""
            INSERT INTO adjudication_results (id, session_id, winning_team, gov_total_score, opp_total_score, clash_table, speaker_scores, created_at)
            VALUES (gen_random_uuid(), :session_id, :winning_team, :gov_total_score, :opp_total_score, :clash_table, :speaker_scores, NOW())
            ON CONFLICT (session_id) DO UPDATE SET
              winning_team = EXCLUDED.winning_team,
              gov_total_score = EXCLUDED.gov_total_score,
              opp_total_score = EXCLUDED.opp_total_score,
              clash_table = EXCLUDED.clash_table,
              speaker_scores = EXCLUDED.speaker_scores,
              created_at = NOW()
        """)
        
        db.execute(query, {
            "winning_team": verdict,
            "gov_total_score": gov_score,
            "opp_total_score": opp_score,
            "clash_table": json.dumps(clash_table),
            "speaker_scores": json.dumps(speaker_scores),
            "session_id": session_id
        })
        
        db.commit()
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to store adjudication: {type(e).__name__}: {str(e)}")
        db.rollback()
        return False


def get_adjudication_result(
    db: Session,
    session_id: str
) -> Optional[Dict]:
    """
    Retrieve cached adjudication result.
    
    Args:
        db: Database session
        session_id: Debate session ID
        
    Returns:
        Adjudication dict or None if not found
    """
    try:
        query = text("""
            SELECT
              winning_team,
              gov_total_score,
              opp_total_score,
              clash_table,
              speaker_scores,
              created_at
            FROM adjudication_results
            WHERE session_id = :session_id
        """)
        
        result = db.execute(query, {"session_id": session_id}).fetchone()
        
        if not result:
            return None
        
        return {
            "winning_team": result[0],
            "gov_total_score": result[1],
            "opp_total_score": result[2],
            "clash_table": result[3] if isinstance(result[3], dict) else json.loads(result[3]) if result[3] else {},
            "speaker_scores": result[4] if isinstance(result[4], list) else json.loads(result[4]) if result[4] else [],
            "adjudicated_at": result[5]
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to retrieve adjudication: {type(e).__name__}: {str(e)}")
        return None


def update_debate_with_adjudication(
    db: Session,
    session_id: str,
    verdict: str,
    gov_score: float,
    opp_score: float
) -> bool:
    """
    Quick update to mark debate as adjudicated with verdict + scores.
    (Used if you want to store without full clash_table initially)
    
    Args:
        db: Database session
        session_id: Debate session ID
        verdict: Winning team
        gov_score: Government score (0-100)
        opp_score: Opposition score (0-100)
        
    Returns:
        True if successful
    """
    try:
        query = text("""
            INSERT INTO adjudication_results (id, session_id, winning_team, gov_total_score, opp_total_score, clash_table, speaker_scores, created_at)
            VALUES (gen_random_uuid(), :session_id, :winning_team, :gov_total_score, :opp_total_score, '{}', '[]', NOW())
            ON CONFLICT (session_id) DO UPDATE SET
              winning_team = EXCLUDED.winning_team,
              gov_total_score = EXCLUDED.gov_total_score,
              opp_total_score = EXCLUDED.opp_total_score
        """)
        
        db.execute(query, {
            "winning_team": verdict,
            "gov_total_score": gov_score,
            "opp_total_score": opp_score,
            "session_id": session_id
        })
        
        db.commit()
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update debate: {type(e).__name__}: {str(e)}")
        db.rollback()
        return False


def get_debates_by_verdict(
    db: Session,
    verdict: str,
    limit: int = 10
) -> list:
    """
    Get all debates with a specific verdict.
    
    Args:
        db: Database session
        verdict: Verdict to filter by ("Government", "Opposition")
        limit: Max results
        
    Returns:
        List of debate records
    """
    try:
        query = text("""
            SELECT
              session_id,
              winning_team as verdict,
              gov_total_score as gov_score,
              opp_total_score as opp_score,
              created_at as adjudicated_at
            FROM adjudication_results
            WHERE winning_team = :verdict
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        results = db.execute(query, {
            "verdict": verdict,
            "limit": limit
        }).fetchall()
        
        return [
            {
                "session_id": r[0],
                "verdict": r[1],
                "gov_score": r[2],
                "opp_score": r[3],
                "adjudicated_at": r[4]
            }
            for r in results
        ]
        
    except Exception as e:
        print(f"[ERROR] Failed to query debates: {type(e).__name__}: {str(e)}")
        return []
