from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    OPENAI_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = None

    model_config = ConfigDict(env_file=".env", extra="allow")

settings = Settings()