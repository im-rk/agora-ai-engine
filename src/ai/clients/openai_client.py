from openai import OpenAI
from src.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)