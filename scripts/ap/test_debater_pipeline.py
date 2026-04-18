"""
Sandbox Test: AP Debater 4-Phase Pipeline
Purpose: Test full AP debate pipeline orchestration
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.ai.agents.debater import DebaterAgent
from src.core.redis_client import get_redis_async
from src.schemas.ap.matches import APRole, DebateSide


async def test_debater_pipeline():
    """Test full 4-phase debater pipeline."""
    print("Testing Debater 4-Phase Pipeline...")
    
    db = None
    redis_client = None
    
    try:
        # Initialize
        redis_client = await get_redis_async()
        debater = DebaterAgent(redis_client=redis_client)
        
        # Sample AP debate transcript
        sample_transcript = """
        PM: "This house believes free trade agreements benefit all nations. First, they increase competition and consumer choice."
        
        LO: "That's not necessarily true. Free trade can harm domestic industries and workers through outsourcing."
        """
        
        # AP test parameters
        speaker_role = APRole.GOVERNMENT_WHIP.value
        speaker_id = "test:debater:ap:gw_001"
        match_id = str(uuid.uuid4())
        
        # Test 1: Phase 1 - Clash Matrix
        print("\n[Phase 1] Parsing Clash Matrix...")
        clash_matrix = await debater.phase1_parse_clash_matrix(sample_transcript, match_id)
        print(f"[PASS] Clash matrix generated")
        print(f"   - Opponent claims: {len(clash_matrix.get('opponent_claims', []))} identified")
        print(f"   - Dropped args: {len(clash_matrix.get('our_dropped_args', []))} identified")
        print(f"   - Vulnerabilities: {len(clash_matrix.get('vulnerabilities', []))} identified")
        
        # Test 2: Phase 2 - Query Synthesis
        print("\n[Phase 2] Generating Search Queries...")
        queries = await debater.phase2_generate_search_queries(clash_matrix, speaker_role, match_id)
        print(f"[PASS] Generated {len(queries)} search queries")
        for i, q in enumerate(queries, 1):
            print(f"   [{i}] {q}")
        
        # Test 3: Phase 3 - Retrieve & Rerank
        print("\n[Phase 3] Retrieving Evidence...")
        evidence = await debater.phase3_retrieve_and_rerank(queries, top_k=3)
        print(f"[PASS] Retrieved {len(evidence)} top evidence pieces")
        for i, e in enumerate(evidence, 1):
            score = e.get('score', 0)
            text = e.get('text', '')[:80]
            print(f"   [{i}] Score: {score:.2f} - {text}...")
        
        # Test 4: Phase 4 - Generate Response with Streaming
        print("\n[Phase 4] Generating Response (Streaming)...")
        response = await debater.phase4_generate_response_streaming(
            clash_matrix=clash_matrix,
            speaker_role=speaker_role,
            evidence=evidence,
            speaker_id=speaker_id,
            personality_trait="balanced",
            session_id=match_id
        )
        print(f"[PASS] Response generated ({len(response)} chars)")
        print(f"   First 150 chars: {response[:150]}...")
        
        # Test 5: Full Orchestration
        print("\n[Full Orchestration] Testing orchestrate_debater_response...")
        full_response = await debater.orchestrate_debater_response(
            transcript=sample_transcript,
            speaker_role=speaker_role,
            speaker_id=speaker_id,
            personality_trait="balanced",
            session_id=match_id
        )
        print(f"[PASS] Full orchestration successful")
        print(f"   Response length: {len(full_response)} chars")
        print(f"   Response preview: {full_response[:150]}...\n")
        
        print("[PASS] Debater Pipeline Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] Debater Pipeline Test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if redis_client:
            await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(test_debater_pipeline())
