from src.core.database import SessionLocal
from src.models.debate import DebateSession
from sqlalchemy import text
from uuid import UUID

def analyze():
    db = SessionLocal()
    uid = 'a3f1e827-f0ca-4113-b8f9-c7ee29929fe6'
    
    # 1. Total matches
    total = db.query(DebateSession).filter(DebateSession.user_id == UUID(uid)).count()
    
    # 2. Matches by status
    status_counts = db.execute(text("SELECT status, count(*) FROM debate_sessions WHERE user_id = :uid GROUP BY status"), {'uid': uid}).fetchall()
    
    # 3. Matches with adjudication results
    adj_count = db.execute(text("SELECT count(*) FROM adjudication_results WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid)"), {'uid': uid}).scalar()
    
    # 4. Matches that reached the end (have turn 5 or 6)
    finished_turns = db.execute(text("SELECT count(distinct session_id) FROM turns WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid) AND turn_number >= 5"), {'uid': uid}).scalar()

    print(f"User: {uid}")
    print(f"Total Matches: {total}")
    print(f"Status Breakdown: {status_counts}")
    print(f"Adjudication Results: {adj_count}")
    print(f"Matches with 5+ turns: {finished_turns}")

if __name__ == "__main__":
    analyze()
