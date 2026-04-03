from openai import OpenAI
from src.core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)