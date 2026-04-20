"""
Adjudication Worker: Background task that runs when debate ends.

Triggered by Redis consumer when all speakers finish.
Runs the 5-phase adjudication pipeline and saves results to database.

Process:
1. Extract transcript from Redis state
2. Call adjudicator.orchestrate_adjudication()
3. Run all 5 phases (40-60 seconds)
4. Save results to database
5. Publish ADJUDICATION_COMPLETE event to frontend
"""

import json
import logging
import asyncio
from typing import Optional

import redis.asyncio as redis

from src.ai.agents.adjudicator import AdjudicatorAgent
from src.core.database import SessionLocal
from src.repositories.adjudication_repo import store_adjudication_result
from src.schemas.state_schema import LiveMatchState

logger = logging.getLogger(__name__)


async def run_adjudication_worker(
    client: redis.Redis,
    channel: str,
    match_id: str,
    state: LiveMatchState
) -> bool:
    """
    Background worker that runs adjudication when debate ends.

    Flow:
    1. Extract transcript from state
    2. Publish "adjudication started" to frontend
    3. Run 5-phase adjudication pipeline (returns raw dict)
    4. Parse raw dict → AdjudicationResult Pydantic object
    5. Save to database via result.to_database_dict()
    6. Publish ADJUDICATION_COMPLETE with verdict to frontend
    """
    try:
        logger.info(
            f"[ADJUDICATION WORKER] Starting adjudication for match {match_id}..."
        )

        # STEP 1: Extract transcript from state
        transcript_text = _format_transcript(state.transcript)
        speaker_roles = [turn.role for turn in state.schedule]

        logger.debug(
            f"[ADJUDICATION WORKER] Transcript: {len(transcript_text)} chars, "
            f"{len(speaker_roles)} speakers"
        )

        # STEP 2: Notify frontend that adjudication has begun
        await client.publish(channel, json.dumps({
            "event": "ADJUDICATION_STARTED",
            "match_id": match_id,
            "message": "AI Adjudication in progress (Phase 1/5)..."
        }))
        logger.info(f"[ADJUDICATION WORKER] Published ADJUDICATION_STARTED")

        # STEP 3: Run the 5-phase pipeline
        # NOTE: orchestrate_adjudication() returns a plain dict, NOT a Pydantic object.
        adjudicator = AdjudicatorAgent()
        result_dict = await adjudicator.orchestrate_adjudication(
            transcript=transcript_text,
            debate_format="AP",
            speaker_roles=speaker_roles,
            session_id=match_id
        )

        # STEP 4: Parse raw dict → AdjudicationResult Pydantic object
        # This is REQUIRED because:
        #   - result.winning_team is a computed @property on PillarBreakdown
        #   - result.to_database_dict() is a method on AdjudicationResult
        # Neither exists on a plain dict — this was the original critical bug.
        from src.schemas.adjudication import (
            AdjudicationResult, MacroClash, WCMEntry,
            PillarBreakdown, PillarScore, AdjudicationSummary, SpeakerScore
        )

        # Phase 3 may nest pillars under "pillars" key or directly at top level
        pillar_data = result_dict.get("pillar_breakdown", {})
        pillar_pillars = pillar_data.get("pillars", pillar_data)

        # Phase 4 nests the list under "speaker_scores" key inside the dict
        raw_speaker_scores = result_dict.get("speaker_scores", {})
        if isinstance(raw_speaker_scores, dict):
            speaker_scores_list = raw_speaker_scores.get("speaker_scores", [])
        else:
            speaker_scores_list = raw_speaker_scores  # already a flat list

        result = AdjudicationResult(
            clashes=[MacroClash(**c) for c in result_dict.get("clashes", [])],
            wcm_matrix=[WCMEntry(**w) for w in result_dict.get("wcm_matrix", [])],
            net_logic_score=result_dict.get("net_logic_score", 0.0),
            pillar_breakdown=PillarBreakdown(
                matter=PillarScore(**pillar_pillars["matter"]),
                manner=PillarScore(**pillar_pillars["manner"]),
                method=PillarScore(**pillar_pillars["method"]),
                role=PillarScore(**pillar_pillars["role"]),
                pillar_reasoning=pillar_data.get("pillar_reasoning", "")
            ),
            speaker_scores=[SpeakerScore(**s) for s in speaker_scores_list],
            summary=AdjudicationSummary(**result_dict.get("summary", {})),
            session_id=match_id
        )

        logger.info(
            f"[ADJUDICATION WORKER] Adjudication complete! "
            f"Winner: {result.winning_team}, "
            f"Gov: {result.government_score} — Opp: {result.opposition_score}"
        )

        # STEP 5: Save to Supabase database
        db = SessionLocal()
        try:
            adjudication_dict = result.to_database_dict()
            success = store_adjudication_result(db, match_id, adjudication_dict)
            if not success:
                logger.error(f"[ADJUDICATION WORKER] DB store failed for {match_id}")
            else:
                logger.info(f"[ADJUDICATION WORKER] Result saved to DB for {match_id}")
        except Exception as db_error:
            logger.exception(
                f"[ADJUDICATION WORKER] DB error for {match_id}: {type(db_error).__name__}"
            )
        finally:
            db.close()

        # STEP 6: Push final verdict to frontend via Redis → Go → WebSocket
        await client.publish(channel, json.dumps({
            "event": "ADJUDICATION_COMPLETE",
            "match_id": match_id,
            "status": "completed",
        
        logger.info(
            f"[ADJUDICATION WORKER] Final verdict published for {match_id}"
        )
        
        return True
        
    except Exception as e:
        logger.exception(
            f"[ADJUDICATION WORKER] Error adjudicating {match_id}: "
            f"{type(e).__name__}: {str(e)}"
        )
        
        # Publish error event so frontend knows
        try:
            await client.publish(channel, json.dumps({
                "event": "ADJUDICATION_ERROR",
                "match_id": match_id,
                "status": "error",
                "error": f"Adjudication failed: {type(e).__name__}",
                "message": f"Failed to adjudicate debate. Error: {str(e)[:100]}"
            }))
        except Exception as pub_error:
            logger.error(
                f"[ADJUDICATION WORKER] Failed to publish error event: {type(pub_error).__name__}"
            )
        
        return False


def _format_transcript(transcript_list: list) -> str:
    """
    Convert transcript from list format to readable string for LLM.
    
    Input format (from Redis state):
    [
        {"role": "Prime Minister", "text": "Today we debate..."},
        {"role": "Leader of Opposition", "text": "We stand firmly..."}
    ]
    
    Output format (for LLM):
    "Prime Minister: Today we debate...
     Leader of Opposition: We stand firmly..."
    
    Args:
        transcript_list: List of transcript items from state.transcript
        
    Returns:
        Formatted transcript string
    """
    if not transcript_list:
        return ""
    
    lines = []
    for item in transcript_list:
        if isinstance(item, dict):
            role = item.get("role", "Unknown")
            text = item.get("text", "")
        else:
            # Fallback if not a dict
            continue
        
        if text:
            lines.append(f"{role}: {text}")
    
    return "\n".join(lines)
