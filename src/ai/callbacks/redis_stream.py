"""
Redis Stream Callback: Publishes LLM tokens to Redis in real-time.

Enables streaming responses where each token is published to a Redis
stream channel, allowing frontend to display text as it's generated.

Flow:
  LLM starts → AI_THOUGHT_START
    ↓ (per token)
  Generate token → AI_TOKEN
    ↓ (when done)
  LLM ends → AI_THOUGHT_COMPLETE
"""

import json
from langchain_core.callbacks import AsyncCallbackHandler


class RedisStreamingCallbackHandler(AsyncCallbackHandler):
    """Publishes LLM lifecycle events and tokens to Redis stream."""

    def __init__(self, redis_client, channel: str):
        """
        Initialize callback handler.
        
        Args:
            redis_client: redis.asyncio.Redis client instance
            channel: Redis PubSub channel name (e.g., "debate:speaker_5:response")
        """
        self.redis_client = redis_client
        self.channel = channel

    async def on_llm_start(self, serialized: dict, prompts: list, **kwargs) -> None:
        """Publish event when LLM starts processing prompt."""
        event = {"event": "AI_THOUGHT_START"}
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM started. Published AI_THOUGHT_START to {self.channel}")

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Publish each token as it's generated (streaming)."""
        event = {
            "event": "AI_TOKEN",
            "text": token
        }
        await self.redis_client.publish(self.channel, json.dumps(event))

    async def on_llm_end(self, response, **kwargs) -> None:
        """Publish event when LLM finishes generating response."""
        event = {"event": "AI_THOUGHT_COMPLETE"}
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM finished. Published AI_THOUGHT_COMPLETE to {self.channel}")

    async def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Publish error event if LLM fails."""
        event = {
            "event": "AI_ERROR",
            "error_message": "The AI lost its train of thought. Please try again.",
            "error_type": type(error).__name__
        }
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM Error: {error}")

    
    
