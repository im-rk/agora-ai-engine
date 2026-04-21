import asyncio
import sys
from src.core.database import SessionLocal
from src.models.debate import DebateSession

def check_db():
    db = SessionLocal()
    try:
        sessions = db.query(DebateSession).all()
        print(f"Total sessions: {len(sessions)}")
        for s in sessions:
            print(f"ID: {s.id}, User ID: {s.user_id}, Format: {s.format}, Status: {s.status}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
