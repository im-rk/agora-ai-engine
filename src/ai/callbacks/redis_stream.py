import json
from langchain_core.callbacks import AsyncCallbackHandler

class RedisStreamingCallbackHandler(AsyncCallbackHandler):

    def __init__(self,redis_client,channel:str):
        """Catches tokens and lifecycle events from the LLM and fires them into Redis."""
        self.redis_client=redis_client
        self.channel=channel

    async def on_llm_start(self, serialized: dict, prompts: list, **kwargs) -> None:
        """Runs the millisecond the LLM receives the prompt."""
        start_event = {
            "event": "AI_THOUGHT_START"
        }
        await self.redis_client.publish(self.channel, json.dumps(start_event))
        print(f"LLM started thinking. Fired AI_THOUGHT_START to {self.channel}")
    
    async def on_llm_new_token(self,token:str,**kwargs)->None:
        """Runs the millisecond the LLM generates a new word."""
        chunk_event={
            "event":"AI_TOKEN",
            "text":token
        }
        await self.redis_client.publish(self.channel,json.dumps(chunk_event))
    
    async def on_llm_end(self,response,**kwargs)->None:
        """Runs the exact millisecond the LLM finishes the final word."""
        end_event={
            "event":"AI_THOUGHT_COMPLETE"
        }
        await self.redis_client.publish(self.channel,json.dumps(end_event))
        print(f"LLM finished generating. Fired AI_THOUGHT_COMPLETE to {self.channel}")

    async def on_llm_error(self,error:Exception,**kwargs)->None:
        """Runs if Groq/OpenAI crashes a time out."""
        error_event={
            "event":"AI_ERROR",
            "error_message":"The AI lost its train of thought. Please try again."
        }

        await self.redis_client.publish(self.channel,json.dumps(error_event))
        print(f"LLM Error:{error}")

    
    
