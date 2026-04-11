"""
Groq Client: Configurable interface for Groq LLM API.

Groq is used for fast, cost-effective completions alongside OpenAI.
Uses singleton pattern with caching for efficiency.
Supports streaming for real-time token delivery to Redis.
"""

from functools import lru_cache
from langchain_groq import ChatGroq
from src.core.config import settings


@lru_cache(maxsize=1)
def get_groq_client(
    model: str = "llama-3.1-8b-instant",
    temperature: float = 0.7,
    streaming: bool = False
) -> ChatGroq:
    """
    Get Groq client instance (cached singleton).
    
    Creates a single instance on first call, then returns the cached instance
    for all subsequent calls. Significantly more efficient than creating
    a new instance per request.
    
    Args:
        model: Groq model name (default: llama-3.1-8b-instant)
        temperature: Sampling temperature (0-1, default: 0.7)
        streaming: Enable token streaming (default: False)
            - True: Tokens streamed to callbacks (real-time UI)
            - False: Full response returned at once
    
    Returns:
        ChatGroq client instance (cached and reused)
    
    Raises:
        ValueError: If GROQ_API_KEY is not configured
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured in environment")
    
    return ChatGroq(
        model=model,
        temperature=temperature,
        streaming=streaming,
        api_key=settings.GROQ_API_KEY,
        max_tokens=2048
    )
