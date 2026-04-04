from openai import OpenAI
from langchain_openai import ChatOpenAI
from src.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def get_openai_client(model: str = "gpt-4o-mini", temperature: float = 0.7) -> ChatOpenAI:
    """Returns ChatOpenAI client (supports both sync invoke() and async ainvoke())."""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY
    )