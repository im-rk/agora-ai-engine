from langchain_core.prompts import ChatPromptTemplate


def get_adjudicator_prompt() -> ChatPromptTemplate:
    system_message = """
You are an expert debate adjudicator.

You must:
- Evaluate both teams fairly
- Compare arguments, rebuttals, and logic
- Decide a winner
- Assign scores out of 100 for each team

Return ONLY structured output.
"""

    human_message = """
Debate Transcript:
{transcript}

Evaluate the debate and provide:
- winning_team ("Government" or "Opposition")
- gov_total_score
- opp_total_score
- speaker_scores (role → score)
- feedback (short paragraph)
"""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", human_message)
    ])