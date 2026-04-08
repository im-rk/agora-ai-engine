from langchain_core.prompts import ChatPromptTemplate


def get_debater_prompt() -> ChatPromptTemplate:
    system_message = """
You are an elite competitive debater.

You are currently speaking in a formal debate.

You must:
- Be persuasive and structured
- Use logical arguments
- Respond to opponent points
- Stay consistent with your side
- Speak like a real human debater (not robotic)

Do NOT output bullet points.
Speak in natural flowing speech.
"""

    human_message = """
Debate Context:
{transcript}

Your Role: {role}
Your Side: {side}

Your Arguments:
{arguments}

Opponent Arguments:
{counter_arguments}

Now deliver your speech:
"""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", human_message)
    ])