import cohere
from src.core.config import settings

co = cohere.Client(settings.COHERE_API_KEY)