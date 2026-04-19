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
    
    This task runs asynchronously and doesn't block the Redis consumer.
    
    Flow:
    1. Extract transcript from state
    2. Publish "started" event to frontend
    3. Run 5-phase adjudication pipeline
    4. Save results to database
    5. Publish "completed" event with verdict
    
    Args:
        client: Redis client for publishing updates
        channel: Redis channel (debate:match_id:turns)
        match_id: Debate session ID
        state: Complete debate state with transcript from Redis
        
    Returns:
        True if successful, False if failed
    """
    try:
        logger.info(
            f"[ADJUDICATION WORKER] Starting adjudication for match {match_id}..."
        )
        
        # ===== STEP 1: Extract transcript from state =====
        transcript_text = _format_transcript(state.transcript)
        speaker_roles = [turn.role for turn in state.schedule]
        
        logger.debug(
            f"[ADJUDICATION WORKER] Extracted transcript: "
            f"{len(transcript_text)} chars, {len(speaker_roles)} speakers"
        )
        
        # ===== STEP 2: Publish "adjudication started" event =====
        await client.publish(channel, json.dumps({
            "event": "ADJUDICATION_STARTED",
            "match_id": match_id,
            "message": "AI Adjudication in progress (Phase 1/5)..."
        }))
        
        logger.info(f"[ADJUDICATION WORKER] Published ADJUDICATION_STARTED event")
        
        # ===== STEP 3: Run adjudication pipeline =====
        adjudicator = AdjudicatorAgent()
        
        logger.info(
            f"[ADJUDICATION WORKER] Starting 5-phase pipeline for {match_id}..."
        )
        
        result = await adjudicator.orchestrate_adjudication(
            transcript=transcript_text,
            debate_format="AP",  # AP format by default (6 speakers)
            speaker_roles=speaker_roles,
            session_id=match_id
        )
        
        logger.info(
            f"[ADJUDICATION WORKER] Adjudication complete! "
            f"Winner: {result['winning_team']}, "
            f"Score: {result['gov_total_score']}-{result['opp_total_score']}"
        )
        
        # ===== STEP 4: Save to database =====
        db = SessionLocal()
        try:
            adjudication_dict = result.to_database_dict()
            success = store_adjudication_result(db, match_id, adjudication_dict)
            
            if not success:
                logger.error(
                    f"[ADJUDICATION WORKER] Failed to store result for {match_id}"
                )
                # Continue anyway - publish what we have
            else:
                logger.info(
                    f"[ADJUDICATION WORKER] Result saved to database for {match_id}"
                )
                
        except Exception as db_error:
            logger.exception(
                f"[ADJUDICATION WORKER] Database error for {match_id}: {type(db_error).__name__}"
            )
        finally:
            db.close()
        
        # ===== STEP 5: Publish final verdict to frontend =====
        await client.publish(channel, json.dumps({
            "event": "ADJUDICATION_COMPLETE",
            "match_id": match_id,
            "status": "completed",
            "verdict": result['winning_team'],
            "gov_score": result['gov_total_score'],
            "opp_score": result['opp_total_score'],
            "clash_table": {
                "clashes": [c.__dict__ if hasattr(c, '__dict__') else c for c in result['clashes']],
                "wcm_matrix": [w.__dict__ if hasattr(w, '__dict__') else w for w in result['wcm_matrix']],
                "net_logic_score": result['net_logic_score']
            },
            "summary": result['summary'].__dict__ if hasattr(result['summary'], '__dict__') else result['summary']
        }))
        
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
