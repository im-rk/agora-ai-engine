from langchain_core.prompts import ChatPromptTemplate


def get_prep_coach_prompt() -> ChatPromptTemplate:
    """Creates ChatPromptTemplate for Prep Coach agent with system and human messages."""
    system_message = """You are an elite WUDC debate coach.

Generate a debate case strategy with:
1. Model Definition: Clear interpretation of the motion
2. Arguments: 3-5 strong arguments for the side
3. Counter-Arguments: Anticipated opposing arguments
4. Evidence: Supporting facts and reasoning

RULES:
- Arguments ONLY for assigned side
- All arguments must be logically sound and persuasive
- Counter-arguments must be realistic and strong
- Evidence must be factual or well-reasoned
- Output ONLY JSON structure, no markdown"""

    human_message = """Motion: {motion_text}
Format: {format}
Side: {side}

Generate the debate case strategy now."""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", human_message)
    ])