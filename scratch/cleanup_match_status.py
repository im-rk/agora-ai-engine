from src.core.database import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_match_statuses():
    db = SessionLocal()
    try:
        # Find all session_ids that have an adjudication result but are not marked as FINISHED
        query = text("""
            UPDATE debate_sessions
            SET status = 'FINISHED', ended_at = (
                SELECT created_at FROM adjudication_results 
                WHERE adjudication_results.session_id = debate_sessions.id 
                LIMIT 1
            )
            WHERE id IN (SELECT session_id FROM adjudication_results)
            AND status != 'FINISHED'
        """)
        
        result = db.execute(query)
        db.commit()
        logger.info(f"Successfully updated {result.rowcount} matches to FINISHED status.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_match_statuses()
