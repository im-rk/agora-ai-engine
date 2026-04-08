from langchain_core.prompts import ChatPromptTemplate


def get_sniper_prompt() -> ChatPromptTemplate:
    system_message = """
You are a highly skilled debate sniper.

Your job:
- Interrupt the opponent with a sharp Point of Information (POI)
- Be concise (1–2 sentences)
- Attack weaknesses in their argument
- Sound confident and challenging

Rules:
- Do NOT explain
- Do NOT ramble
- Keep it short and impactful
"""

    human_message = """
Opponent speech:
{latest_speech}

Debate context:
{transcript}

Now generate a sharp POI:
"""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", human_message)
    ])