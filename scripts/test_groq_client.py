"""
Sandbox Test: Groq Client
Purpose: Test LLM API connectivity and basic call for AP debate format
"""

import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from src.ai.clients.groq_client import get_groq_client
from src.schemas.ap.matches import APRole, DebateSide


async def test_groq_client():
    """Test Groq LLM client."""
    print("Testing Groq Client...")
    
    try:
        # Test 1: Non-streaming call
        print("\n[Test 1] Testing non-streaming call...")
        llm = get_groq_client(streaming=False, temperature=0.1)
        
        messages = [
            SystemMessage(content="You are an expert Asian Parliamentary debate coach. Provide concise, structured advice."),
            HumanMessage(content="What are the 3 key elements of a strong AP debate argument?")
        ]
        
        response = await llm.ainvoke(messages)
        print(f"[PASS] Non-streaming call successful")
        print(f"   Response length: {len(response.content)} chars")
        print(f"   First 100 chars: {response.content[:100]}...")
        
        # Test 2: Streaming call
        print("\n[Test 2] Testing streaming call...")
        llm_stream = get_groq_client(streaming=True, temperature=0.5)
        
        messages = [
            SystemMessage(content="You are an AP debate coach. Format responses clearly."),
            HumanMessage(content="List 3 AP debate tips in bullet format.")
        ]
        
        stream_response = await llm_stream.ainvoke(messages)
        print(f"[PASS] Streaming call successful")
        print(f"   Response length: {len(stream_response.content)} chars")
        print(f"   Response:\n{stream_response.content[:200]}...")
        
        # Test 3: Verify caching (lru_cache)
        print("\n[Test 3] Testing client caching...")
        client1 = get_groq_client(temperature=0.7)
        client2 = get_groq_client(temperature=0.7)
        
        if client1 is client2:
            print(f"[PASS] Client caching working (same instance returned)")
        else:
            print(f"[WARN] Client caching not working (different instances)")
        
        print("\n[PASS] Groq Client Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] Groq Client Test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_groq_client())
