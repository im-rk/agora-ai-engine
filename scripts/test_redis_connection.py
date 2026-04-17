"""
Sandbox Test: Redis Connection
Purpose: Verify Upstash Redis connectivity for AP match state management
"""

import asyncio
import redis.asyncio as redis
from src.core.config import settings
from datetime import datetime, timezone


async def test_redis_connection():
    """Test basic Redis connectivity."""
    print("Testing Redis Connection...")
    print(f"Redis URL: {settings.REDIS_URL[:50]}...")
    
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Test PING
        pong = await client.ping()
        print(f"[PASS] Redis PING: {pong}")
        
        # Test SET/GET with AP match state key format
        match_id = "match:ap:test:001"
        match_state = '{"status": "AWAITING_PARTICIPANTS", "created_at": "' + datetime.now(timezone.utc).isoformat() + '"}'
        
        await client.set(match_id, match_state, ex=3600)
        print(f"[PASS] SET {match_id} = AP match state")
        
        retrieved = await client.get(match_id)
        print(f"[PASS] GET {match_id} = {retrieved[:60]}...")
        
        # Test PUBLISH/SUBSCRIBE with AP match channel
        channel = "ap:match:state:updates"
        message = '{"match_id": "test:001", "status": "DEBATE_IN_PROGRESS"}'
        
        # Publish a message
        result = await client.publish(channel, message)
        print(f"[PASS] PUBLISH to {channel}: {result} subscribers received")
        
        # Clean up
        await client.delete(match_id)
        print(f"[PASS] Cleaned up test AP match key")
        
        print("\n[PASS] Redis Connection Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] Redis Connection Test FAILED: {e}\n")
        return False
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(test_redis_connection())
