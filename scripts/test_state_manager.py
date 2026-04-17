"""
Sandbox Test: State Manager
Purpose: Test saving and retrieving AP debate state from Redis
"""

import asyncio
import uuid
from datetime import datetime, timezone
from src.engine.state import state_manager
from src.schemas.ap.matches import APRole, DebateSide


async def test_state_manager():
    """Test state manager save and retrieve."""
    print("Testing State Manager...")
    
    try:
        # Create test match ID
        match_id = str(uuid.uuid4())
        print(f"Match ID: {match_id}")
        
        # Test 1: Initialize a new AP match state
        print("\n[Test 1] Initializing AP match state...")
        state = await state_manager.initialize_match(
            match_id=match_id,
            human_side=DebateSide.GOVERNMENT.value,
            format_type="AP"
        )
        print(f"[PASS] State initialized: {state.match_id}")
        print(f"   - Match ID: {state.match_id}")
        print(f"   - Status: {state.status}")
        print(f"   - Current turn index: {state.current_turn_index}")
        
        # Test 2: Add to transcript with AP roles
        print("\n[Test 2] Adding AP turns to transcript...")
        state.transcript.append({
            "speaker_role": APRole.PRIME_MINISTER.value,
            "content": "This house believes technology improves lives. First, productivity increases."
        })
        state.transcript.append({
            "speaker_role": APRole.LEADER_OF_OPPOSITION.value,
            "content": "We oppose. Technology creates inequality and job displacement."
        })
        print(f"[PASS] Added 2 AP turns to transcript")
        
        # Test 3: Update state in Redis
        print("\n[Test 3] Persisting state to Redis...")
        await state_manager.update_state(state)
        print(f"[PASS] State persisted to Redis")
        
        # Test 4: Retrieve state from Redis
        print("\n[Test 4] Retrieving AP state from Redis...")
        retrieved_state = await state_manager.get_state(match_id)
        print(f"[PASS] AP state retrieved from Redis")
        print(f"   - Transcript turns: {len(retrieved_state.transcript)}")
        print(f"   - Turn 1: {retrieved_state.transcript[0]['speaker_role']}")
        print(f"   - Turn 2: {retrieved_state.transcript[1]['speaker_role']}")
        
        # Test 5: Verify data integrity
        print("\n[Test 5] Verifying AP data integrity...")
        assert len(retrieved_state.transcript) == 2
        assert retrieved_state.transcript[0]["content"] == "This house believes technology improves lives. First, productivity increases."
        assert retrieved_state.transcript[1]["content"] == "We oppose. Technology creates inequality and job displacement."
        print(f"[PASS] Data integrity verified")
        
        print("\n[PASS] AP State Manager Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] State Manager Test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_state_manager())
