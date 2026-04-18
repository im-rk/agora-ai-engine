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
from src.engine.state import state_manager
from .ai_response_generator import (
    generate_ai_response,
    persist_human_turn,
)

logger = logging.getLogger(__name__)


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
            channel = message["channel"]
            # Extract match_id from channel format: "debate:{match_id}:turns"
            parts = channel.split(":")
            match_id = parts[1] if len(parts) > 1 else None
            if not match_id:
                continue
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
                            asyncio.create_task(
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
                                f"Listening for Deepgram bytes..."
                            )
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
                                    f"[CONSUMER] Previous turn was HUMAN ({previous_speaker.role}). "
                                    f"Persisting to Supabase..."
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
                                    state=state
                                )

                                if not persist_success:
                                    logger.error(
                                        f"[CONSUMER] Failed to persist human turn for "
                                        f"match {match_id}"
                                    )
                                    # Continue anyway - don't block the debate

                    # Check if debate is complete
                    if state.current_turn_index >= len(state.schedule):
                        logger.info(
                            f"[CONSUMER] All turns complete for match {match_id}. "
                            f"Marking finished..."
                        )
                        state.status = "finished"
                        await state_manager.update_state(state)
                        # TODO Step 4: wire adjudication here
                        await client.publish(channel, json.dumps({
                            "event": "MATCH_COMPLETE",
                            "message": "All speeches delivered. Adjudication starting..."
                        }))
                        continue

                    # Determine and trigger next speaker
                    if state.schedule and state.current_turn_index < len(state.schedule):
                        next_speaker = state.schedule[state.current_turn_index]
                        if next_speaker.player_type == "ai":
                            logger.info(
                                f"[CONSUMER] It is the {next_speaker.role}'s turn (AI). "
                                f"Generating response..."
                            )
                            asyncio.create_task(
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
                                f"Waiting for Deepgram bytes from Go gateway..."
                            )
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


async def generate_ai_response(
    client: redis.Redis,
    channel: str,
    match_id: str,
    state: object
):
    """
    Execute 4-phase debate pipeline with streaming.
    
    Phases:
    1. State Tracking: Parse transcript into clash matrix
    2. Query Synthesis: Generate targeted search queries
    3. Retrieve & Re-Rank: Find best evidence
    4. Generation: Stream response via Redis callbacks
    
    Args:
        client: Redis async client
        channel: Redis channel (e.g., "debate:{match_id}:events")
        match_id: Unique match identifier (DebateSession UUID)
        state: LiveMatchState object from state_manager
    """
    db = None
    try:
        # Validate state before proceeding
        if not state.schedule or state.current_turn_index >= len(state.schedule):
            logger.error(f"Invalid state for match {match_id}: schedule empty or index out of bounds")
            return
        
        # Get current speaker info
        current_speaker = state.schedule[state.current_turn_index]
        speaker_role = current_speaker.role  
        speaker_id = f"{match_id}:{state.current_turn_index}"
        
        # Reconstruct debate transcript from state history
        transcript = reconstruct_transcript(state)
        
        logger.info(f"Starting 4-phase pipeline for {speaker_role} (speaker_id: {speaker_id})")
        logger.debug(f"Transcript length: {len(transcript)} chars")
        
        # Initialize debater agent
        debater = DebaterAgent(redis_client=client)
        
        # Execute 4-phase orchestration (streaming to Redis)
        # session_id is the DebateSession ID for logging all LLM calls
        response = await debater.orchestrate_debater_response(
            transcript=transcript,
            speaker_role=speaker_role,
            speaker_id=speaker_id,
            personality_trait="balanced",
            session_id=match_id
        )
        
        logger.info(f"AI Response generated ({len(response)} chars): {response[:100]}...")
        
        # STEP 3: Persist the generated response back to state
        # Create turn object with speaker role and content
        turn_data = {
            "speaker_role": speaker_role,
            "speaker_side": current_speaker.side,
            "content": response,
            "player_type": "ai"
        }
        
        # Append to transcript (in-memory state)
        if not hasattr(state, 'transcript'):
            state.transcript = []
        state.transcript.append(turn_data)
        logger.debug(f"Appended {speaker_role} ({current_speaker.side}) response to transcript. Total turns: {len(state.transcript)}")
        
        # Save updated state back to Redis
        await state_manager.update_state(state)
        logger.debug(f"State persisted to Redis for match {match_id}")
        
        # STEP 4: Save turn to database
        db = SessionLocal()
        
        create_turn_func = APMatchRepository.create_turn
        if hasattr(state, 'format_type') and state.format_type.upper() == "BP":
            from src.repositories.bp.matches import BPMatchRepository
            create_turn_func = BPMatchRepository.create_turn
            
        turn = create_turn_func(
            db=db,
            session_id=match_id,
            turn_number=state.current_turn_index,
            speaker_role=speaker_role,
            speaker_type=SpeakerType.AI.value,
            transcript_text=response,
            duration_seconds=0  # Will be updated if we have timing data
        )
        logger.info(f"Turn record created in database: {turn.id}")

        db.commit()   # Makes the turn record permanent in the database
        logger.debug(f"Turn record committed to database: {turn.id}")

        
    except Exception as e:
        logger.exception(f"Error in generate_ai_response: {e}")
        # Publish error event to Redis
        error_event = {
            "event": "AI_ERROR",
            "error_message": f"Failed to generate response: {str(e)}"
        }
        await client.publish(channel, json.dumps(error_event))
    finally:
        if db:
            db.close()


def reconstruct_transcript(state: object) -> str:
    """
    Reconstruct debate transcript from state history.
    
    Concatenates all previous turns with speaker role, side, and content.
    Used to provide context to DebaterAgent for response generation.
    
    Args:
        state: LiveMatchState object
    
    Returns:
        Formatted debate transcript string
    """
    if not hasattr(state, 'transcript') or not state.transcript:
        return "Debate just started. This is the opening speech."
    
    transcript_lines = []
    for turn in state.transcript:
        speaker_role = turn.get("speaker_role", "Unknown")
        speaker_side = turn.get("speaker_side", "")
        content = turn.get("content", "")
        
        # Format: "ROLE (SIDE): content"
        if speaker_side:
            header = f"{speaker_role} ({speaker_side}): {content}"
        else:
            header = f"{speaker_role}: {content}"
        
        transcript_lines.append(header)
    
    return "\n\n".join(transcript_lines)

