"""
Sandbox Test: State Manager
Purpose: Test saving and retrieving debate state from Redis
"""

import asyncio
import uuid
from src.engine.state import state_manager


async def test_state_manager():
    """Test state manager save and retrieve."""
    print("Testing State Manager...")
    
    try:
        # Create test match ID
        match_id = str(uuid.uuid4())
        print(f"Match ID: {match_id}")
        
        # Test 1: Initialize a new match state
        print("\n[Test 1] Initializing match state...")
        state = await state_manager.initialize_match(
            match_id=match_id,
            human_side="affirmative",
            format_type="BP"
        )
        print(f"[PASS] State initialized: {state.match_id}")
        print(f"   - Match ID: {state.match_id}")
        print(f"   - Status: {state.status}")
        print(f"   - Current turn index: {state.current_turn_index}")
        
        # Test 2: Add to transcript
        print("\n[Test 2] Adding turns to transcript...")
        state.transcript.append({
            "speaker_role": "PM",
            "content": "This is the prime minister's opening statement."
        })
        state.transcript.append({
            "speaker_role": "LO",
            "content": "This is the leader of opposition's rebuttal."
        })
        print(f"[PASS] Added 2 turns to transcript")
        
        # Test 3: Update state in Redis
        print("\n[Test 3] Persisting state to Redis...")
        await state_manager.update_state(state)
        print(f"[PASS] State persisted to Redis")
        
        # Test 4: Retrieve state from Redis
        print("\n[Test 4] Retrieving state from Redis...")
        retrieved_state = await state_manager.get_state(match_id)
        print(f"[PASS] State retrieved from Redis")
        print(f"   - Transcript turns: {len(retrieved_state.transcript)}")
        print(f"   - Turn 1: {retrieved_state.transcript[0]['speaker_role']}")
        print(f"   - Turn 2: {retrieved_state.transcript[1]['speaker_role']}")
        
        # Test 5: Verify data integrity
        print("\n[Test 5] Verifying data integrity...")
        assert len(retrieved_state.transcript) == 2
        assert retrieved_state.transcript[0]["content"] == "This is the prime minister's opening statement."
        assert retrieved_state.transcript[1]["content"] == "This is the leader of opposition's rebuttal."
        print(f"[PASS] Data integrity verified")
        
        print("\n[PASS] State Manager Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] State Manager Test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_state_manager())
