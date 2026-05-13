import json
from langchain_core.callbacks import AsyncCallbackHandler
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.state_schema import LiveMatchState


class RedisStreamingCallbackHandler(AsyncCallbackHandler):
    """
    Publishes LLM lifecycle events and tokens to Redis.
    
    Optionally buffers tokens in match state for rejoin recovery (full generation strategy).
    """

    def __init__(
        self,
        redis_client,
        channel: str,
        state: Optional["LiveMatchState"] = None,
        state_manager = None
    ):
        """
        Initialize callback handler.
        
        Args:
            redis_client: redis.asyncio.Redis client instance
            channel: Redis PubSub channel name (e.g., "debate:{match_id}:turns")
            state: Optional LiveMatchState for token buffering (rejoin recovery)
            state_manager: Optional state manager for persisting buffered tokens
        """
        self.redis_client = redis_client
        self.channel = channel
        self.state = state
        self.state_manager = state_manager

    async def on_llm_start(self, serialized: dict, prompts: list, **kwargs) -> None:
        """Publish event when LLM starts processing prompt."""
        event = {"event": "AI_THOUGHT_START"}
        await self.redis_client.publish(self.channel, json.dumps(event))
        print(f"LLM started. Published AI_THOUGHT_START to {self.channel}")

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Publish each token as it's generated (streaming).
        
        If state and state_manager provided, also buffer token in Redis state
        for rejoin recovery (full generation strategy).
        """
        # Always publish for live streaming to gateway/frontend
        event = {
            "event": "AI_TOKEN",
            "text": token
        }
        await self.redis_client.publish(self.channel, json.dumps(event))
        
        # NEW: If state provided, buffer token for rejoin recovery
        if self.state and self.state_manager:
            # Accumulate in buffer
            self.state.active_stream_buffer += token
            
            # CRITICAL: Persist to Redis immediately
            # This ensures buffer survives gateway disconnects/crashes
            await self.state_manager.update_state(self.state)

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

    
    
