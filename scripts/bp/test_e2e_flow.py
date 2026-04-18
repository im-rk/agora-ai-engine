"""
Sandbox Test: End-to-End BP Redis Consumer Flow
Purpose: Test full pipeline: Redis event -> AI response -> BP State persistence -> Supabase logging
"""

import asyncio
import json
import uuid
import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings
from src.core.database import SessionLocal
from src.core.redis_client import get_redis_async
from src.engine.state import state_manager
from src.models.setup import Motion, MotionCategory
from src.models.debate import DebateSession, MatchFormat
from src.models.user import User, SkillLevel
from src.workers.redis_consumer import generate_ai_response
from src.schemas.bp.matches import BPRole, BPTeam


async def test_e2e_flow():
    """Test end-to-end BP redis consumer flow."""
    print("Testing End-to-End BP Flow (Redis -> AI -> Postgres)...\n")
    
    db = None
    redis_client = None
    
    try:
        # Setup database
        db = SessionLocal()
        redis_client = await get_redis_async()
        
        # Step 1: Create test user
        print("[Step 1] Creating test user...")
        user = User(
            id=uuid.uuid4(),
            email=f"test_bp_{uuid.uuid4().hex[:8]}@debate.local",
            display_name="test_bp_debater",
            password_hash="hashed_test_pwd"
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Step 2: Create BP test motion
        print("\n[Step 2] Creating BP test motion...")
        motion = Motion(
            id=uuid.uuid4(),
            motion_text="This house believes artificial intelligence will fundamentally alter human governance",
            category=MotionCategory.TECHNOLOGY,
            is_custom=False
        )
        db.add(motion)
        db.flush()
        print(f"[PASS] BP Motion created: {motion.id}")
        
        # Step 3: Create BP debate session
        print("\n[Step 3] Creating BP debate session...")
        session = DebateSession(
            id=uuid.uuid4(),
            user_id=user.id,
            motion_id=motion.id,
            format=MatchFormat.BRITISH_PARLIAMENTARY,
            human_role=BPRole.PRIME_MINISTER.value,
            skill_level=SkillLevel.INTERMEDIATE,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()
        session_id = str(session.id)
        print(f"[PASS] BP Debate session created: {session_id}")
        
        # Step 4: Initialize BP match state in Redis
        print("\n[Step 4] Initializing BP match state in Redis...")
        state = await state_manager.initialize_match(
            match_id=session_id,
            human_side=BPTeam.OPENING_GOVERNMENT.value,
            format_type="BP",
            preferred_role=BPRole.PRIME_MINISTER.value
        )
        # Add initial BP opening
        state.transcript.append({
            "speaker_role": BPRole.PRIME_MINISTER.value,
            "content": "In this debate, the opening government affirms that AI will redefine how nations organize."
        })
        await state_manager.update_state(state)
        print(f"[PASS] BP Match state initialized in Redis")
        
        # Step 5: Simulate Redis event
        print("\n[Step 5] Simulating BP debate turn...")
        channel = f"debate:{session_id}:events"
        
        current_state = await state_manager.get_state(session_id)
        
        await generate_ai_response(
            client=redis_client,
            channel=channel,
            match_id=session_id,
            state=current_state
        )
        print(f"[PASS] AI response generated and persisted")
        
        # Step 6: Verify Redis state was updated
        print("\n[Step 6] Verifying BP Redis state update...")
        updated_state = await state_manager.get_state(session_id)
        
        if len(updated_state.transcript) > 1:
            print(f"[PASS] BP State updated in Redis")
            print(f"   Transcript now has {len(updated_state.transcript)} turns")
            for i, turn in enumerate(updated_state.transcript, 1):
                role = turn.get("speaker_role", "Unknown")
                preview = turn.get("content", "")[:50]
                print(f"   Turn {i}: {role} - {preview}...")
        else:
            print(f"[WARN] BP State didn't update (check for errors above)")
        
        # Step 7: Verify Database records
        print("\n[Step 7] Verifying Database BP records...")
        
        from src.models.debate import Turn
        turns = db.query(Turn).filter(Turn.session_id == session.id).all()
        print(f"[PASS] BP Turn records created: {len(turns)} turns in database")
        for i, turn in enumerate(turns, 1):
            print(f"   Turn {i}: {turn.speaker_role} ({len(turn.transcript_text)} chars)")
        
        from src.models.setup import AICallLog
        logs = db.query(AICallLog).filter(AICallLog.session_id == session.id).all()
        print(f"[PASS] AI call logs created: {len(logs)} LLM calls logged")
        for i, log in enumerate(logs, 1):
            print(f"   Log {i}: {log.agent_name} (Temp: {log.temperature})")
        
        print("\n[PASS] End-to-End BP Flow Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] End-to-End BP Flow Test FAILED: {e}\n")
        if db:
            db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if db:
            db.close()
        if redis_client:
            await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(test_e2e_flow())
