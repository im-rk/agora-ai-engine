import asyncio
from src.core.redis_client import redis_client

async def test_redis_connection():
    print("Connecting to Upstash Redis in Mumbai...")
    try:
        # 1. Test the basic connection (Ping)
        response = await redis_client.ping()
        if response:
            print("PING SUCCESS: Python is talking to Redis!")
            
        # 2. Test writing and reading data
        await redis_client.set("agora_test", "Walkie-talkie is working!")
        read_value = await redis_client.get("agora_test")
        print(f" DATA SUCCESS: Retrieved message -> '{read_value}'")
        
        # 3. Clean up our mess
        await redis_client.delete("agora_test")
        print("Cleanup complete. Ready for production.")

    except Exception as e:
        print("\n ERROR: Could not connect to Redis.")
        print(f"Details: {e}")
        print("\nTroubleshooting Checklist:")
        print("- Did you use 'rediss://' (with the 's') in your .env?")
        print("- Is your password exactly correct with no extra spaces?")
    finally:
        # Always close the connection gracefully
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_redis_connection())