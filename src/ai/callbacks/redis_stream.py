import json
from datetime import datetime, timezone
from langchain_core.callbacks import AsyncCallbackHandler


class RedisStreamingCallbackHandler(AsyncCallbackHandler):
    """Publishes LLM lifecycle events and tokens to Redis stream."""

    def __init__(self, redis_client, channel: str, match_id: str = None, turn_index: int = None):
        """
        Initialize callback handler.
        
        Args:
            redis_client: redis.asyncio.Redis client instance
            channel: Redis PubSub channel name (e.g., "debate:speaker_5:response")
            match_id: Optional match UUID for turn timing updates
            turn_index: Optional turn number for timing updates
        """
        self.redis_client = redis_client
        self.channel = channel
        self.match_id = match_id
        self.turn_index = turn_index
        self.start_time = None  # Capture LLM start timestamp

    async def on_llm_start(self, serialized: dict, prompts: list, **kwargs) -> None:
        """Publish event when LLM starts processing prompt."""
        self.start_time = datetime.now(timezone.utc)
        event = {
            "event": "AI_THOUGHT_START",
            "timestamp_utc": self.start_time.isoformat()
        }
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
        end_time = datetime.now(timezone.utc)
        duration_ms = None
        
        # Calculate duration if we captured start time
        if self.start_time:
            duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
        
        event = {
            "event": "AI_THOUGHT_COMPLETE",
            "timestamp_utc": end_time.isoformat(),
            "duration_ms": duration_ms
        }
        
        # Include match_id and turn_index if available (for turn timing updates)
        if self.match_id:
            event["match_id"] = self.match_id
        if self.turn_index is not None:
            event["turn_index"] = self.turn_index
        
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM finished. Published AI_THOUGHT_COMPLETE to {self.channel} (duration: {duration_ms}ms)")

    async def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Publish error event if LLM fails."""
        event = {
            "event": "AI_ERROR",
            "error_message": "The AI lost its train of thought. Please try again.",
            "error_type": type(error).__name__
        }
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM Error: {error}")

    
    
