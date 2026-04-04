from groq import Groq
from src.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)


def ask_llm(system_prompt: str, user_prompt: str):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content