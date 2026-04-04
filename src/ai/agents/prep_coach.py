"""
Prep Coach Agent: Generates structured debate case preparation.

This module is isolated from database and HTTP layers.
Contains only the core async function to generate case prep.
"""

from src.schemas.prep_coach_schema import AIPrepResult


async def generate_case_prep(
    motion_text: str,
    side: str,
    format: str
) -> dict:
    """
    Generates structured debate case preparation using OpenAI with LangChain.
    
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

    prompt = get_prep_coach_prompt()
    llm = get_openai_client(model="gpt-4o-mini", temperature=0.7)
    structured_llm = llm.with_structured_output(AIPrepResult)
    chain = prompt | structured_llm

    result = await chain.ainvoke({
        "motion_text": motion_text,
        "side": side,
        "format": format
    })

    return result.model_dump()
