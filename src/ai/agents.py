from src.services.llm_service import ask_llm
from src.ai.prompts import PREP_COACH_SYSTEM_PROMPT
import json
import re

def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return None

def generate_case_prep(motion: str, side: str, skill_level: str):
    prompt = f"""
Motion: {motion}
Side: {side}
Skill Level: {skill_level}
"""

    full_prompt = PREP_COACH_SYSTEM_PROMPT + "\n" + prompt

    response = ask_llm(full_prompt)

    try:
        cleaned = extract_json(response)

        if not cleaned:
            raise ValueError("No valid JSON found")

        data = json.loads(cleaned)
        return data

    except Exception as e:
        print("\n RAW LLM RESPONSE:\n", response)
        raise e