from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    GROQ_API_KEY : str
    SUPABASE_URL: str
    SUPABASE_KEY:str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_HOST: str

    class Config:
        env_file = ".env"

settings = Settings()
