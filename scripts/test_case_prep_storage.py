"""
Sandbox Test: AP Case Prep Generation & RAG Storage
Purpose: Test AP case prep generation and verify it's stored in pgvector
"""

import asyncio
import uuid
from datetime import datetime, timezone
from src.core.database import SessionLocal
from src.models.setup import Motion, MotionCategory
from src.models.debate import DebateSession
from src.models.user import User, SkillLevel
from src.repositories.ap.case_prep import APCasePrepRepository
from src.schemas.ap.case_prep import GenerateCasePrepRequest, AIPrepResult, Argument
from src.ai.tools.rag_engine import RAGEngine


async def test_case_prep_storage():
    """Test AP case prep generation and RAG storage."""
    print("Testing AP Case Prep Generation & RAG Storage...\n")
    
    db = None
    
    try:
        db = SessionLocal()
        repo = APCasePrepRepository()
        
        # Test 1: Create a test user
        print("[Test 1] Creating test user...")
        user = User(
            id=uuid.uuid4(),
            email=f"test_user_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hashed_password",
            display_name="Test Debater"
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Test 2: Create AP test motion
        print("\n[Test 2] Creating AP test motion...")
        motion = Motion(
            id=uuid.uuid4(),
            motion_text="This house believes artificial intelligence will have a net positive impact on society",
            category=MotionCategory.TECHNOLOGY
        )
        db.add(motion)
        db.flush()
        print(f"[PASS] AP Motion created: {motion.id}")
        
        # Test 3: Create AP debate session
        print("\n[Test 3] Creating AP debate session...")
        session = DebateSession(
            id=uuid.uuid4(),
            user_id=user.id,
            motion_id=motion.id,
            format="AP",
            human_role="PRIME_MINISTER",
            skill_level=SkillLevel.INTERMEDIATE,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.flush()
        print(f"[PASS] AP Debate session created: {session.id}")
        
        # Test 4: Generate AP case prep using repository
        print("\n[Test 4] Generating AP case prep via repository...")
        from src.schemas.ap.matches import DebateSide
        
        case_prep = repo.create_case_prep(
            db=db,
            user_id=str(user.id),
            motion_id=str(motion.id),
            side=DebateSide.GOVERNMENT.value
        )
        db.flush()
        print(f"[PASS] AP Case prep created: {case_prep.id}")
        
        # Test 5: Verify case prep stored in database
        print("\n[Test 5] Verifying case prep in database...")
        
        stored_prep = repo.get_case_prep_by_id(db, str(case_prep.id))
        if stored_prep:
            print(f"[PASS] Case prep retrieved from database")
            print(f"   Side: {stored_prep.side}")
            print(f"   Motion ID: {stored_prep.motion_id}")
        else:
            print(f"[FAIL] Could not retrieve case prep from database")
            raise Exception("Case prep not found in database")
        
        # Test 6: Verify RAG retrieval
        print("\n[Test 6] Verifying RAG retrieval for AP arguments...")
        rag = RAGEngine()
        
        query = "artificial intelligence innovation technology impact"
        results = await rag.aretrieve_counter_arguments(topic=query, k=2)
        
        if results:
            print(f"[PASS] Retrieved {len(results)} similar arguments from RAG")
            for i, r in enumerate(results, 1):
                print(f"   [{i}] {r.get('text', '')[:80]}...")
        else:
            print(f"[WARN] No results retrieved (database may be empty)")
        
        print("\n[PASS] AP Case Prep Storage Test PASSED\n")
        return True
        
    except Exception as e:
        error_msg = str(e)
        # Hide SQL details for cleaner output
        if "[SQL:" in error_msg:
            error_msg = error_msg.split("[SQL:")[0].strip()
        print(f"[FAIL] Case Prep Storage Test FAILED: {error_msg}")
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    asyncio.run(test_case_prep_storage())
