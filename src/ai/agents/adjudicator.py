from src.ai.prompts.adjudicator_prompts import get_adjudicator_prompt
from src.ai.clients.openai_client import get_openai_client

from src.schemas.adjudicator_schema import AdjudicationResultSchema

from src.engine.state import state_manager
from src.core.database import SessionLocal
from src.models.results import AdjudicationResult


async def adjudicate_match(match_id: str):
    """
    Adjudicator Agent:
    Evaluates full debate and stores result in DB.
    """

    # -------------------------
    # 1. Get State
    # -------------------------
    state = await state_manager.get_state(match_id)
    if not state or not state.transcript:
        return

    # -------------------------
    # 2. Format Transcript
    # -------------------------
    formatted_transcript = "\n".join([
        f"{t['speaker']}: {t['text']}"
        for t in state.transcript
    ])

    # -------------------------
    # 3. Prompt + LLM
    # -------------------------
    prompt = get_adjudicator_prompt()

    llm = get_openai_client(
        model="gpt-4o-mini",
        temperature=0.3
    )

    structured_llm = llm.with_structured_output(AdjudicationResultSchema)

    chain = prompt | structured_llm

    # -------------------------
    # 4. Invoke
    # -------------------------
    result = await chain.ainvoke({
        "transcript": formatted_transcript
    })

    result_data = result.model_dump()

    # -------------------------
    # 5. Save to DB
    # -------------------------
    db = SessionLocal()

    adjudication = AdjudicationResult(
        session_id=match_id,
        winning_team=result_data["winning_team"],
        gov_total_score=result_data["gov_total_score"],
        opp_total_score=result_data["opp_total_score"],
        clash_table={},  # placeholder (can improve later)
        speaker_scores=result_data["speaker_scores"]
    )

    db.add(adjudication)
    db.commit()
    db.close()

    return result_data