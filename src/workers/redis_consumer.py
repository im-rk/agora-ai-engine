"""
Redis consumer for debate event orchestration.

This module implements a background worker that listens for debate events
on Redis pub/sub channels and coordinates the appropriate handlers:

- START_MATCH: Checks who speaks first, triggers AI if needed
- TURN_CHANGED: Reads updated state from Redis, triggers next AI turn if applicable
- Match completion: Marks debate as finished and triggers adjudication

Event Channel Pattern:
    debate:{match_id}:turns - Main event channel for each debate match
    
    Expected events:
    {
        "action": "START_MATCH",  # Debate beginning
        "action": "TURN_CHANGED", # Turn incremented by Go gateway
        "action": "..." # Other events
    }
"""

import asyncio
import json
import logging

import redis.asyncio as redis

from src.core.config import settings
from src.core.database import SessionLocal
from src.engine.state import state_manager
from src.repositories.ap.matches import APMatchRepository
from .ai_response_generator import (
    generate_ai_response,
    persist_human_turn,
)
from .adjudication_worker import run_adjudication_worker

logger = logging.getLogger(__name__)

# Global dictionary to track active async tasks per match_id
# This prevents overlapping AI responses when a match is restarted or triggered twice
# Format: { match_id: asyncio.Task }
active_tasks = {}


def cancel_active_task(match_id: str):
    """Cancel any existing async task for the given match_id."""
    if match_id in active_tasks:
        task = active_tasks[match_id]
        if not task.done():
            logger.info(f"[CONSUMER] Cancelling existing task for match {match_id}")
            task.cancel()
        del active_tasks[match_id]


async def start_redis_consumer():
    """
    Background worker that listens for debate events and triggers AI responses.

    Continuously subscribes to Redis pub/sub channel pattern 'debate:*' to receive:
    1. START_MATCH events - Check who speaks first
    2. TURN_CHANGED events - Determine next speaker and trigger AI if applicable
    3. Match completion - Mark debate as finished

    Event Processing:
    - Extracts match_id from channel: "debate:{match_id}:turns"
    - Parses JSON event data to determine action
    - Spawns async tasks for AI response generation
    - Handles errors gracefully without stopping the consumer

    Logs all events with [CONSUMER] prefix for debugging.
    """
    redis_url = settings.REDIS_URL
    client = redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()

    # Listen to ALL match events: turns, completions, errors, etc.
    # Pattern: debate:{match_id}:* catches all events
    await pubsub.psubscribe("debate:*")
    logger.info(
        "[CONSUMER] Python AI Worker is actively listening to all debate events "
        "(debate:*)..."
    )

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            raw_channel = message["channel"]
            # Extract match_id from channel format: "debate:{match_id}:*"
            parts = raw_channel.split(":")
            match_id = parts[1] if len(parts) > 1 else None
            if not match_id:
                continue
            # CRITICAL: Always normalize to :turns - this is the channel the Go
            # gateway (and thus the frontend WebSocket) subscribes to.
            # Without this, events published to :events are invisible to React.
            channel = f"debate:{match_id}:turns"
            raw_data = message["data"]

            logger.debug(f"[CONSUMER] Python heard on {channel}: {raw_data}")

            try:
                data = json.loads(raw_data)
                action = data.get("action")
                event_type = data.get("event")

                # EVENT: START_MATCH - Debate beginning
                if action == "START_MATCH":
                    logger.info(
                        f"[CONSUMER] Match {match_id} Kickoff! "
                        f"Checking who goes first..."
                    )
                    state = await state_manager.get_state(match_id)

                    if state and state.schedule and state.current_turn_index < len(state.schedule):
                        current_speaker = state.schedule[state.current_turn_index]
                        if current_speaker.player_type == "ai":
                            logger.info(
                                f"[CONSUMER] AI ({current_speaker.role}) speaks first! "
                                f"Starting 4-phase debate pipeline..."
                            )
                            cancel_active_task(match_id)
                            active_tasks[match_id] = asyncio.create_task(
                                generate_ai_response(
                                    client=client,
                                    channel=channel,
                                    match_id=match_id,
                                    state=state
                                )
                            )
                        else:
                            logger.info(
                                f"[CONSUMER] Human ({current_speaker.role}) speaks first. "
                                f"Notifying frontend..."
                            )
                            # Tell React it's the human's turn immediately
                            await client.publish(channel, json.dumps({
                                "event": "TURN_STARTED",
                                "speaker": "human",
                                "role": current_speaker.role,
                                "turn_index": state.current_turn_index,
                            }))
                    else:
                        logger.warning(
                            f"[CONSUMER] Invalid state for match {match_id}: "
                            f"no schedule or out of bounds"
                        )

                # EVENT: TURN_CHANGED - Turn incremented by Go gateway
                elif action == "TURN_CHANGED":
                    # Go just incremented the turn in Redis state.
                    # Python reads the full state from Redis (Go already updated it).
                    logger.debug(
                        f"[CONSUMER] TURN_CHANGED received for match {match_id}"
                    )

                    # Read the FULL state from Redis that Go just updated
                    state = await state_manager.get_state(match_id)

                    if not state:
                        logger.warning(
                            f"[CONSUMER] No Python state found for match {match_id}."
                        )
                        continue

                    logger.debug(
                        f"[CONSUMER] Current turn index: {state.current_turn_index}"
                    )

                    # Persist previous human turn if it was human
                    if state.current_turn_index > 0:
                        previous_turn_index = state.current_turn_index - 1
                        if previous_turn_index < len(state.schedule):
                            previous_speaker = state.schedule[previous_turn_index]

                            if previous_speaker.player_type == "human":
                                logger.info(
                                    f"[CONSUMER] Previous speaker ({previous_turn_index}): "
                                    f"{previous_speaker.role} (Human)"
                                )
                                logger.info(
                                    f"[CONSUMER] Persisting HUMAN turn to database..."
                                )

                                # Go has already:
                                # 1. Buffered all HUMAN_TRANSCRIPT_CHUNK events
                                # 2. Combined them into final text in Redis
                                # 3. Updated Redis Scoreboard
                                # 4. Advanced current_turn_index

                                # Now Python's job is to save to Supabase
                                persist_success = await persist_human_turn(
                                    client=client,
                                    match_id=match_id,
                                    state=state,
                                    timing_data={
                                        "duration_ms": data.get("human_speech_duration_ms"),
                                        "start_time_utc": data.get("human_speech_start_time_utc"),
                                        "end_time_utc": data.get("human_speech_end_time_utc"),
                                    }
                                )

                                if persist_success:
                                    logger.info(
                                        f"[CONSUMER] Human turn persisted successfully "
                                        f"for {previous_speaker.role}"
                                    )
                                else:
                                    logger.error(
                                        f"[CONSUMER] Failed to persist human turn for "
                                        f"match {match_id} ({previous_speaker.role})"
                                    )
                                    # Continue anyway - don't block the debate
                            else:
                                logger.debug(
                                    f"[CONSUMER] Previous speaker ({previous_turn_index}): "
                                    f"{previous_speaker.role} (AI - skip persistence)"
                                )
                    
                    # Update AI turn timing if frontend provided it
                    if state.current_turn_index > 0:
                        previous_turn_index = state.current_turn_index - 1
                        if previous_turn_index < len(state.schedule):
                            previous_speaker = state.schedule[previous_turn_index]
                            
                            if previous_speaker.player_type == "ai":
                                # ✅ Extract frontend-measured timing from TURN_CHANGED event
                                ai_speech_duration_ms = data.get("ai_speech_duration_ms")
                                ai_speech_start_time_utc = data.get("ai_speech_start_time_utc")
                                ai_speech_end_time_utc = data.get("ai_speech_end_time_utc")
                                
                                if ai_speech_duration_ms is not None:
                                    logger.info(
                                        f"[CONSUMER] Received AI speech timing for match {match_id}, "
                                        f"turn {previous_turn_index}: {ai_speech_duration_ms}ms"
                                    )
                                    
                                    try:
                                        db = SessionLocal()
                                        
                                        # Determine repository based on match format
                                        match_data_ap = APMatchRepository.get_match_with_motion(db, match_id)
                                        match_repository = APMatchRepository
                                        
                                        if not match_data_ap:
                                            from src.repositories.bp.matches import BPMatchRepository
                                            match_repository = BPMatchRepository
                                        
                                        # Update turn with frontend timing
                                        duration_seconds = ai_speech_duration_ms / 1000.0
                                        match_repository.update_turn_timing(
                                            db=db,
                                            match_id=match_id,
                                            turn_index=previous_turn_index,
                                            duration_seconds=duration_seconds,
                                            started_at=ai_speech_start_time_utc,
                                            ended_at=ai_speech_end_time_utc
                                        )
                                        
                                        logger.info(
                                            f"[CONSUMER] AI turn timing updated for match {match_id}, "
                                            f"turn {previous_turn_index}: {duration_seconds:.2f}s "
                                            f"(frontend-measured)"
                                        )
                                        db.close()
                                    except Exception as e:
                                        logger.error(
                                            f"[CONSUMER] Failed to update AI turn timing: {e}"
                                        )
                                        if db:
                                            db.close()

                    # Check if debate is complete
                    if state.current_turn_index >= len(state.schedule):
                        logger.info(
                            f"[CONSUMER] All turns complete for match {match_id}. "
                            f"Marking finished..."
                        )
                        state.status = "finished"
                        await state_manager.update_state(state)
                        
                        # Publish to frontend that debate is complete
                        await client.publish(channel, json.dumps({
                            "event": "MATCH_COMPLETE",
                            "match_id": match_id,
                            "message": "All speeches delivered. Adjudication starting..."
                        }))
                        
                        # TRIGGER ASYNC ADJUDICATION WORKER
                        # This runs in background, doesn't block the consumer
                        logger.info(
                            f"[CONSUMER] Starting async adjudication worker for {match_id}..."
                        )
                        cancel_active_task(match_id)
                        active_tasks[match_id] = asyncio.create_task(
                            run_adjudication_worker(
                                client=client,
                                channel=channel,
                                match_id=match_id,
                                state=state
                            )
                        )
                        
                        continue

                    # Determine and trigger next speaker
                    if state.schedule and state.current_turn_index < len(state.schedule):
                        next_speaker = state.schedule[state.current_turn_index]
                        if next_speaker.player_type == "ai":
                            logger.info(
                                f"[CONSUMER] It is the {next_speaker.role}'s turn (AI). "
                                f"Generating response..."
                            )
                            cancel_active_task(match_id)
                            active_tasks[match_id] = asyncio.create_task(
                                generate_ai_response(
                                    client=client,
                                    channel=channel,
                                    match_id=match_id,
                                    state=state
                                )
                            )
                        else:
                            logger.info(
                                f"[CONSUMER] It is the {next_speaker.role}'s turn (Human). "
                                f"Notifying frontend..."
                            )
                            # Tell React it's the human's turn so the mic button activates
                            await client.publish(channel, json.dumps({
                                "event": "TURN_STARTED",
                                "speaker": "human",
                                "role": next_speaker.role,
                                "turn_index": state.current_turn_index,
                            }))
                    else:
                        logger.warning(
                            f"[CONSUMER] Turn index {state.current_turn_index} is beyond "
                            f"schedule length {len(state.schedule) if state.schedule else 0}"
                        )

                # EVENT: Other - Match finished or unrecognized action
                else:
                    logger.debug(f"[CONSUMER] Match {match_id} is finished!")

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.exception(f"[CONSUMER] Error: {e}")



