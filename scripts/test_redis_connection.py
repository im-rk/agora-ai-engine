"""
Sandbox Test: Redis Connection
Purpose: Verify Upstash Redis connectivity and basic operations
"""

import asyncio
import redis.asyncio as redis
from src.core.config import settings


async def test_redis_connection():
    """Test basic Redis connectivity."""
    print("Testing Redis Connection...")
    print(f"Redis URL: {settings.REDIS_URL[:50]}...")
    
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Test PING
        pong = await client.ping()
        print(f"[PASS] Redis PING: {pong}")
        
        # Test SET/GET
        test_key = "test:sandbox:key"
        test_value = "hello_from_python"
        
        await client.set(test_key, test_value, ex=3600)
        print(f"[PASS] SET {test_key} = {test_value}")
        
        retrieved = await client.get(test_key)
        print(f"[PASS] GET {test_key} = {retrieved}")
        
        # Test PUBLISH/SUBSCRIBE
        channel = "test:sandbox:channel"
        message = {"test": "message from sandbox"}
        
        # Publish a message
        result = await client.publish(channel, str(message))
        print(f"[PASS] PUBLISH to {channel}: {result} subscribers received")
        
        # Clean up
        await client.delete(test_key)
        print(f"[PASS] Cleaned up test key")
        
        print("\n[PASS] Redis Connection Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"[FAIL] Redis Connection Test FAILED: {e}\n")
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_redis_connection())
