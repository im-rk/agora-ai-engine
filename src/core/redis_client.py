import redis.asyncio as redis
from src.core.config import REDIS_URL

# Create async Redis client (no ssl_cert_reqs for redis.asyncio)
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    encoding="utf-8",
    max_connections=10
)

async def get_redis():
    """Dependency injection for FastAPI endpoints."""
    return redis_client

async def close_redis():
    """Close Redis connection gracefully."""
    await redis_client.close()