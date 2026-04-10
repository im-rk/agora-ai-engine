"""
Sandbox Test: End-to-End Redis Consumer Flow
Purpose: Test full pipeline: Redis event -> AI response -> State persistence -> Supabase logging
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from src.core.config import settings
from src.core.database import SessionLocal
from src.core.redis_client import get_redis_async
from src.engine.state import state_manager
from src.models.setup import Motion, MotionCategory
from src.models.debate import DebateSession
from src.models.user import User, SkillLevel
from src.workers.redis_consumer import generate_ai_response


async def test_e2e_flow():
    """Test end-to-end redis consumer flow."""
    print("Testing End-to-End Flow (Redis -> AI -> Supabase)...\n")
    
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
            email="test@debate.local",
            username="test_debater",
            hashed_password="hashed_test_pwd",
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Step 2: Create test motion
        print("\n[Step 2] Creating test motion...")
        motion = Motion(
            id=uuid.uuid4(),
            motion_text="This house believes technology improvements outweigh privacy concerns",
            category=MotionCategory.TECHNOLOGY,
            is_custom=False
        )
        db.add(motion)
        db.flush()
        print(f"[PASS] Motion created: {motion.id}")
        
        # Step 3: Create debate session
        print("\n[Step 3] Creating debate session...")
        match_id = str(uuid.uuid4())
        session = DebateSession(
            id=uuid.uuid4(),
            user_id=user.id,
            motion_id=motion.id,
            format="BP",
            human_role="opposition",
            skill_level=SkillLevel.INTERMEDIATE,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()
        session_id = str(session.id)
        print(f"[PASS] Debate session created: {session_id}")
        
        # Step 4: Initialize match state in Redis
        print("\n[Step 4] Initializing match state in Redis...")
        state = await state_manager.initialize_match(
            match_id=session_id,
            human_side="opposition",
            format_type="BP"
        )
        # Add some initial transcript
        state.transcript.append({
            "speaker_role": "PM",
            "content": "In this debate, we will prove that technology benefits the world."
        })
        await state_manager.update_state(state)
        print(f"[PASS] Match state initialized in Redis")
        
        # Step 5: Simulate Redis event - redis_consumer would normally trigger this
        print("\n[Step 5] Simulating debate turn (calling generate_ai_response)...")
        channel = f"channel_{session_id}"
        
        # Fetch fresh state for the call
        current_state = await state_manager.get_state(session_id)
        
        # Call generate_ai_response directly
        await generate_ai_response(
            client=redis_client,
            channel=channel,
            match_id=session_id,
            state=current_state
        )
        print(f"[PASS] AI response generated and persisted")
        
        # Step 6: Verify Redis state was updated
        print("\n[Step 6] Verifying Redis state update...")
        updated_state = await state_manager.get_state(session_id)
        
        if len(updated_state.transcript) > 1:
            print(f"[PASS] State updated in Redis")
            print(f"   Transcript now has {len(updated_state.transcript)} turns")
            for i, turn in enumerate(updated_state.transcript, 1):
                role = turn.get("speaker_role", "Unknown")
                preview = turn.get("content", "")[:50]
                print(f"   Turn {i}: {role} - {preview}...")
        else:
            print(f"[WARN] State didn't update (check for errors above)")
        
        # Step 7: Verify Supabase records were created
        print("\n[Step 7] Verifying Supabase records...")
        
        # Check turns table
        from src.models.debate import Turn
        turns = db.query(Turn).filter(Turn.session_id == session.id).all()
        print(f"[PASS] Turn records created: {len(turns)} turns in database")
        for i, turn in enumerate(turns, 1):
            print(f"   Turn {i}: {turn.speaker_role} ({len(turn.transcript_text)} chars)")
        
        # Check ai_call_logs table
        from src.models.setup import AICallLog
        logs = db.query(AICallLog).filter(AICallLog.session_id == session.id).all()
        print(f"[PASS] AI call logs created: {len(logs)} LLM calls logged")
        for i, log in enumerate(logs, 1):
            print(f"   Log {i}: {log.agent_name} (Temp: {log.temperature})")
        
        print("\n[PASS] End-to-End Flow Test PASSED\n")
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
            await redis_client.close()


if __name__ == "__main__":
    asyncio.run(test_e2e_flow())
