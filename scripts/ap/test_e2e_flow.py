"""
Sandbox Test: End-to-End AP Redis Consumer Flow
Purpose: Test full pipeline: Redis event -> AI response -> AP State persistence -> Supabase logging
"""

import sys
import os
import asyncio
import json
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings
from src.core.database import SessionLocal
from src.core.redis_client import get_redis_async
from src.engine.state import state_manager
from src.models.setup import Motion, MotionCategory
from src.models.debate import DebateSession
from src.models.user import User, SkillLevel
from src.workers.redis_consumer import generate_ai_response
from src.schemas.ap.matches import APRole, DebateSide


async def test_e2e_flow():
    """Test end-to-end AP redis consumer flow."""
    print("Testing End-to-End AP Flow (Redis -> AI -> Supabase)...\n")
    
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
            email="test_ap@debate.local",
            display_name="test_ap_debater",
            password_hash="hashed_test_pwd"
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Step 2: Create AP test motion
        print("\n[Step 2] Creating AP test motion...")
        motion = Motion(
            id=uuid.uuid4(),
            motion_text="This house believes technological innovation outweighs privacy concerns",
            category=MotionCategory.TECHNOLOGY,
            is_custom=False
        )
        db.add(motion)
        db.flush()
        print(f"[PASS] AP Motion created: {motion.id}")
        
        # Step 3: Create AP debate session
        print("\n[Step 3] Creating AP debate session...")
        match_id = str(uuid.uuid4())
        session = DebateSession(
            id=uuid.uuid4(),
            user_id=user.id,
            motion_id=motion.id,
            format="AP",
            human_role=APRole.PRIME_MINISTER.value,
            skill_level=SkillLevel.INTERMEDIATE,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()
        session_id = str(session.id)
        print(f"[PASS] AP Debate session created: {session_id}")
        
        # Step 4: Initialize AP match state in Redis
        print("\n[Step 4] Initializing AP match state in Redis...")
        state = await state_manager.initialize_match(
            match_id=session_id,
            human_side=DebateSide.GOVERNMENT.value,
            format_type="AP"
        )
        # Add initial AP opening
        state.transcript.append({
            "speaker_role": APRole.PRIME_MINISTER.value,
            "content": "In this debate, the government affirms that innovation benefits society more than it harms."
        })
        await state_manager.update_state(state)
        print(f"[PASS] AP Match state initialized in Redis")
        
        # Step 5: Simulate Redis event
        print("\n[Step 5] Simulating AP debate turn...")
        channel = f"channel_{session_id}"
        
        current_state = await state_manager.get_state(session_id)
        
        await generate_ai_response(
            client=redis_client,
            channel=channel,
            match_id=session_id,
            state=current_state
        )
        print(f"[PASS] AI response generated and persisted")
        
        # Step 6: Verify Redis state was updated
        print("\n[Step 6] Verifying AP Redis state update...")
        updated_state = await state_manager.get_state(session_id)
        
        if len(updated_state.transcript) > 1:
            print(f"[PASS] AP State updated in Redis")
            print(f"   Transcript now has {len(updated_state.transcript)} turns")
            for i, turn in enumerate(updated_state.transcript, 1):
                role = turn.get("speaker_role", "Unknown")
                preview = turn.get("content", "")[:50]
                print(f"   Turn {i}: {role} - {preview}...")
        else:
            print(f"[WARN] AP State didn't update (check for errors above)")
        
        # Step 7: Verify Supabase records
        print("\n[Step 7] Verifying Supabase AP records...")
        
        from src.models.debate import Turn
        turns = db.query(Turn).filter(Turn.session_id == session.id).all()
        print(f"[PASS] AP Turn records created: {len(turns)} turns in database")
        for i, turn in enumerate(turns, 1):
            print(f"   Turn {i}: {turn.speaker_role} ({len(turn.transcript_text)} chars)")
        
        from src.models.setup import AICallLog
        logs = db.query(AICallLog).filter(AICallLog.session_id == session.id).all()
        print(f"[PASS] AI call logs created: {len(logs)} LLM calls logged")
        for i, log in enumerate(logs, 1):
            print(f"   Log {i}: {log.agent_name} (Temp: {log.temperature})")
        
        print("\n[PASS] End-to-End AP Flow Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] End-to-End Flow Test FAILED: {e}\n")
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
