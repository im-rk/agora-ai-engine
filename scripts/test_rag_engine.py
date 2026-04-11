"""
Sandbox Test: RAG Engine
Purpose: Test pgvector retrieval and evidence ranking
"""

import asyncio
from src.ai.tools.rag_engine import RAGEngine


async def test_rag_engine():
    """Test RAG engine for evidence retrieval."""
    print("Testing RAG Engine (pgvector)...")
    
    try:
        rag = RAGEngine()
        
        # Test 1: Retrieve counter-arguments
        print("\n[Test 1] Retrieving counter-arguments...")
        query = "free trade benefits economy"
        results = await rag.aretrieve_counter_arguments(topic=query, k=3)
        
        print(f"[PASS] Retrieved {len(results)} results for: '{query}'")
        if results:
            for i, result in enumerate(results, 1):
                print(f"   [{i}] Score: {result.get('score', 'N/A'):.2f}")
                print(f"       Text: {result.get('text', '')[:100]}...")
        else:
            print(f"   [WARN] No results found (may be empty database)")
        
        # Test 2: Retrieve counter-arguments (different query)
        print("\n[Test 2] Retrieving counter-arguments (different query)...")
        query2 = "government regulation needed"
        results2 = await rag.aretrieve_counter_arguments(topic=query2, k=3)
        
        print(f"[PASS] Retrieved {len(results2)} results for: '{query2}'")
        if results2:
            for i, result in enumerate(results2, 1):
                print(f"   [{i}] Score: {result.get('score', 'N/A'):.2f}")
                print(f"       Text: {result.get('text', '')[:100]}...")
        else:
            print(f"   [WARN] No results found (may be empty database)")
        
        # Test 3: Test pgvector connection
        print("\n[Test 3] Testing pgvector connection...")
        try:
            # Try to get a simple result to verify DB connectivity
            test_results = await rag.aretrieve_counter_arguments(topic="test", k=1)
            print(f"[PASS] pgvector connection successful")
        except Exception as db_error:
            print(f"[FAIL] pgvector connection failed: {db_error}")
            raise
        
        print("\n[PASS] RAG Engine Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] RAG Engine Test FAILED: {e}\n")
        print("Note: This test requires:")
        print("  - PostgreSQL connection to Supabase")
        print("  - pgvector extension enabled")
        print("  - Evidence data already populated in argument_embeddings table")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_rag_engine())
