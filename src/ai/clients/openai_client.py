from openai import OpenAI
from langchain_openai import ChatOpenAI
from src.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


import os

def get_openai_client(temperature: float = 0.7) -> ChatOpenAI:
    """Returns ChatOpenAI client dynamically configured via environment variables."""
    # Use explicitly defined API key for the corresponding service
    api_key = settings.OPENAI_API_KEY

    # If the user is routing to an OpenRouter or Groq OpenAI proxy, use their respective keys if OPENAI_API_KEY isn't covering it.
    if settings.LLM_BASE_URL and "groq" in settings.LLM_BASE_URL.lower():
        api_key = settings.GROQ_API_KEY or api_key

    kwargs = {
        "model": settings.LLM_MODEL,
        "temperature": temperature,
        "api_key": api_key,
    }

    if settings.LLM_BASE_URL:
        kwargs["base_url"] = settings.LLM_BASE_URL

    return ChatOpenAI(**kwargs)