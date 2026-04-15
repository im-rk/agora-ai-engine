"""
Prep Coach Agent: Generates structured debate case preparation.

This module is isolated from database and HTTP layers.
Contains only the core async function to generate case prep.
"""

import json
import re


async def generate_case_prep(
    motion_text: str,
    side: str,
    format: str
) -> dict:
    """
    Generates structured debate case preparation using the configured LLM.

    Args:
        motion_text: The debate motion
        side: Government or Opposition
        format: Debate format (BP/AP)

    Returns:
        dict: Case preparation with model_definition, arguments, counter_arguments, evidence

    Raises:
        ValueError: If LLM fails to produce valid structured output
    """
    from src.ai.prompts.prep_coach_prompts import get_prep_coach_prompt
    from src.ai.clients.openai_client import get_openai_client
    from langchain_core.output_parsers import StrOutputParser

    prompt = get_prep_coach_prompt()
    llm = get_openai_client(temperature=0.7)

    # Use StrOutputParser — robust and compatible with reasoning/thinking models
    # that wrap their answer in a <think> block or a 'reasoning' field.
    chain = prompt | llm | StrOutputParser()

    raw_text = await chain.ainvoke({
        "motion_text": motion_text,
        "side": side,
        "format": format
    })

    if not raw_text:
        raise ValueError("LLM returned an empty response for case prep.")

    # Robustly extract JSON block from anywhere in the model's output.
    # This handles: pure JSON, ```json ... ```, and reasoning-first responses.
    json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Fallback: find first '{' to last '}'
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in LLM response. Raw: {raw_text[:200]}")
        json_str = raw_text[start:end + 1]

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM response: {e}. Raw: {json_str[:200]}")

    if not isinstance(result, dict):
        raise ValueError(f"Parsed JSON is not a dict, got {type(result)}")

    return result
