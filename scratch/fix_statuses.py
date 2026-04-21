from src.core.database import SessionLocal
from src.models.debate import DebateSession, MatchStatus
from sqlalchemy import text
from uuid import UUID

def cleanup():
    db = SessionLocal()
    uid = 'a3f1e827-f0ca-4113-b8f9-c7ee29929fe6'
    
    # Update matches that have at least 4 turns recorded to 'Finished' 
    # even if adjudication didn't save. This matches user's perception of 'completed'.
    query = text("""
        UPDATE debate_sessions 
        SET status = 'Finished', ended_at = NOW() 
        WHERE user_id = :uid 
        AND status = 'Started' 
        AND id IN (
            SELECT session_id FROM turns 
            GROUP BY session_id 
            HAVING count(*) >= 4
        )
    """)
    
    result = db.execute(query, {'uid': uid})
    db.commit()
    print(f"Updated {result.rowcount} matches to Finished status.")
    
    # Also ensure any match with an adjudication result is marked Finished
    query2 = text("""
        UPDATE debate_sessions
        SET status = 'Finished'
        WHERE id IN (SELECT session_id FROM adjudication_results)
        AND status != 'Finished'
    """)
    result2 = db.execute(query2)
    db.commit()
    print(f"Updated {result2.rowcount} matches to Finished (had adj results).")

if __name__ == "__main__":
    cleanup()
