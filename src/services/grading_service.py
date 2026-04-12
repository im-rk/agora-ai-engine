"""
Grading Service — Orchestrates post-debate adjudication.

Called by redis_consumer.trigger_adjudication() when all turns complete.
Does not interact with Redis — only the database and the Adjudicator agent.
"""

from sqlalchemy.orm import Session

from src.ai.agents.adjudicator import AdjudicatorAgent
from src.repositories.results_repo import save_adjudication_result, save_user_performance
from src.repositories.debate_repo import log_ai_call
from src.schemas.state_schema import LiveMatchState


async def run_adjudication(
    db: Session,
    state: LiveMatchState,
    session_id: str,
    user_id: str,
    motion_text: str,
    format_type: str,
    human_speaker_role: str,
) -> dict:
    """
    Full post-debate adjudication pipeline.

    Steps:
    1. Call AdjudicatorAgent with complete match state
    2. Save the full verdict to adjudication_results table
    3. Extract the human speaker's score → save to user_performance table
    4. Log the AI call to ai_call_logs table
    5. Return the verdict (redis_consumer publishes MATCH_COMPLETE with it)

    Args:
        db: SQLAlchemy session
        state: Final LiveMatchState (all turns in .transcript, POIs in .all_pois)
        session_id: The DebateSession ID (also the match_id in Redis)
        user_id: The human debater's User ID
        motion_text: The debate motion text
        format_type: "ap" or "bp"
        human_speaker_role: The role the human played (e.g., "Prime Minister")

    Returns:
        The full verdict dict from AdjudicatorAgent
    """
    print(f"[GradingService] Starting adjudication for session {session_id}...")

    # Step 1: Run AI adjudication
    agent = AdjudicatorAgent()
    verdict = await agent.adjudicate(
        state=state,
        motion_text=motion_text,
        format_type=format_type,
    )

    # Step 2: Save full verdict to adjudication_results table
    save_adjudication_result(
        db=db,
        session_id=session_id,
        winning_team=verdict["winning_team"],
        gov_total_score=verdict["gov_total_score"],
        opp_total_score=verdict["opp_total_score"],
        clash_table=verdict.get("clash_table", []),
        speaker_scores=verdict.get("speaker_scores", []),
    )
    print(f"[GradingService] Verdict saved. Winner: {verdict['winning_team']}")

    # Step 3: Find the human player's score and save to user_performance
    human_score_data = next(
        (
            s for s in verdict.get("speaker_scores", [])
            if s["speaker_role"].lower() == human_speaker_role.lower()
        ),
        None,
    )

    if human_score_data:
        save_user_performance(
            db=db,
            user_id=user_id,
            session_id=session_id,
            speaker_score_data=human_score_data,
        )
        print(f"[GradingService] Human performance saved. Score: {human_score_data['total_score']}/100")
    else:
        print(f"[GradingService] WARN: Could not find human score for role '{human_speaker_role}'")

    # Step 4: Log the AI call
    log_ai_call(
        db=db,
        session_id=session_id,
        agent_name="AdjudicatorAgent",
        prompt_used="ADJUDICATOR_SCORING_PROMPT",
        model_version="gpt-4o-mini",
        temperature=0.2,
        raw_output=str(verdict)[:1000],  # Truncate for storage
    )

    return verdict
