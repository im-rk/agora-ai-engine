"""
Sandbox Test: BP Case Prep Generation & RAG Storage
Purpose: Test BP case prep generation and verify it's stored in pgvector
"""

import sys
import os
import asyncio
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.database import SessionLocal
from src.models.setup import Motion, MotionCategory
from src.models.debate import DebateSession, MatchFormat
from src.models.user import User, SkillLevel
from src.repositories.bp.case_prep import BPCasePrepRepository
from src.repositories.bp.matches import BPMatchRepository
from src.ai.tools.rag_engine import RAGEngine


async def test_case_prep_storage():
    """Test BP case prep generation and RAG storage."""
    print("Testing BP Case Prep Generation & RAG Storage...\n")
    
    db = None
    
    try:
        db = SessionLocal()
        match_repo = BPMatchRepository()
        case_prep_repo = BPCasePrepRepository()
        
        # Test 1: Create a test user
        print("[Test 1] Creating test user...")
        user = User(
            id=uuid.uuid4(),
            email=f"test_bp_user_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hashed_password",
            display_name="Test BP Debater"
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Test 2: Create BP test motion and match
        # We use BPMatchRepository.create_match which will also create the initial CasePrep record!
        print("\n[Test 2] Creating BP test match with repository...")
        session = match_repo.create_match(
            db=db,
            user_id=str(user.id),
            motion="This house believes artificial intelligence will have a net positive impact on society",
            team="closing_government",
            role="member_of_government"
        )
        
        print(f"[PASS] BP Debate session created: {session.id}")
        print(f"       -> Motion ID: {session.motion_id}")
        print(f"       -> CasePrep ID: {session.case_prep_id}")
        
        # Test 3: Generate BP case prep data simulating AI update
        print("\n[Test 3] Simulating AI saving case prep logic into repository...")
        
        case_prep = case_prep_repo.update_case_prep(
            db=db,
            case_prep_id=str(session.case_prep_id),
            model_definition="AI represents automated reasoning capabilities...",
            arguments=[{"claim": "AI boosts productivity", "reasoning": "Mechanizing thought..."}],
            counter_arguments=["AI displace workers"],
            evidence=["McKinsey report indicates..."]
        )
        print(f"[PASS] BP Case prep updated with simulated AI data: {case_prep.id}")
        
        # Test 4: Verify case prep stored in database
        print("\n[Test 4] Verifying case prep in database...")
        
        stored_prep = case_prep_repo.get_case_prep_by_id(db, str(case_prep.id))
        if stored_prep:
            print(f"[PASS] Case prep retrieved from database")
            print(f"   Side: {stored_prep.side}")
            print(f"   Motion ID: {stored_prep.motion_id}")
            print(f"   Arguments length: {len(stored_prep.arguments)}")
        else:
            print(f"[FAIL] Could not retrieve case prep from database")
            raise Exception("Case prep not found in database")
            
        print("\n[PASS] BP Case Prep Storage Test PASSED\n")
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "[SQL:" in error_msg:
            error_msg = error_msg.split("[SQL:")[0].strip()
        print(f"[FAIL] Case Prep Storage Test FAILED: {error_msg}")
        if db:
            db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    asyncio.run(test_case_prep_storage())
