"""
AI response generation for debate turns.

This module handles the 4-phase debate pipeline orchestration:
1. State Tracking: Parse transcript into clash matrix
2. Query Synthesis: Generate targeted search queries
3. Retrieve & Re-Rank: Find best evidence
4. Generation: Stream response via Redis callbacks

Generates AI debate speeches and persists them to both Redis (real-time)
and database (permanent record).
"""

import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as redis

from src.core.database import SessionLocal
from src.engine.state import state_manager
from src.ai.agents.debater import DebaterAgent
from src.repositories.ap.matches import APMatchRepository
from src.models.debate import SpeakerType
from .transcript_handler import reconstruct_transcript

logger = logging.getLogger(__name__)


async def generate_ai_response(
    client: redis.Redis,
    channel: str,
    match_id: str,
    state: object
) -> Optional[str]:
    """
    Execute 4-phase debate pipeline with streaming.

    Orchestrates the complete AI response generation workflow:
    1. Validates match state and schedule
    2. Reconstructs debate transcript for context
    3. Generates AI response using DebaterAgent
    4. Persists response to Redis state and database
    5. Handles errors and publishes status events

    Phases:
        1. State Tracking: Parse transcript into clash matrix
        2. Query Synthesis: Generate targeted search queries
        3. Retrieve & Re-Rank: Find best evidence
        4. Generation: Stream response via Redis callbacks

    Args:
        client: Redis async client for pub/sub operations
        channel: Redis channel (e.g., "debate:{match_id}:turns")
        match_id: Unique match identifier (DebateSession UUID)
        state: LiveMatchState object from state_manager containing
               schedule, transcript, and current_turn_index

    Returns:
        Optional[str]: Generated AI response, or None on error

    Raises:
        Logs exceptions to logger, does not raise

    Example:
        >>> response = await generate_ai_response(
        ...     client=redis_client,
        ...     channel="debate:match-123:turns",
        ...     match_id="match-123",
        ...     state=live_state
        ... )
        >>> print(f"Generated: {response[:50]}...")
    """
    db = None
    try:
        # VALIDATION: Ensure state is valid before proceeding
        if not state.schedule or state.current_turn_index >= len(state.schedule):
            logger.error(
                f"Invalid state for match {match_id}: "
                f"schedule empty or index {state.current_turn_index} out of bounds"
            )
            return None

        # PREPARATION: Extract speaker info and context
        current_speaker = state.schedule[state.current_turn_index]
        speaker_role = current_speaker.role  # e.g., "Prime Minister (PM)", "Government Whip", etc.
        speaker_id = f"{match_id}:{state.current_turn_index}"
        speaker_side = current_speaker.side  # "Government" or "Opposition"

        # Reconstruct debate transcript from state history
        transcript = reconstruct_transcript(state)

        logger.info(
            f"[AI] Starting 4-phase pipeline for {speaker_role} ({speaker_side})"
            f"(speaker_id: {speaker_id})"
        )
        logger.debug(f"[AI] Transcript length: {len(transcript)} chars")

        # PHASE 1-4: Orchestrate AI Response Generation
        # Initialize debater agent for this turn
        debater = DebaterAgent(redis_client=client)

        # Announce to the frontend who is speaking RIGHT NOW
        # This switches the UI from "Waiting..." to the active speaker display
        await client.publish(channel, json.dumps({
            "event": "TURN_STARTED",
            "speaker": "ai",
            "role": speaker_role,  # Full role name with side
            "side": speaker_side,
            "turn_index": state.current_turn_index,
        }))
        logger.info(f"[AI] Published TURN_STARTED for {speaker_role} on {channel}")

        # Execute 4-phase orchestration (streaming to Redis)
        # session_id is the DebateSession ID for logging all LLM calls
        response = await debater.orchestrate_debater_response(
            transcript=transcript,
            speaker_role=speaker_role,  # Full AP role name
            speaker_id=speaker_id,
            personality_trait="balanced",
            session_id=match_id,
            channel=channel
        )

        logger.info(
            f"[AI] Response generated ({len(response)} chars): {response[:100]}..."
        )

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
        logger.debug(
            f"[AI] Appended {speaker_role} ({current_speaker.side}) response to "
            f"transcript. Total turns: {len(state.transcript)}"
        )

        # Save updated state back to Redis
        await state_manager.update_state(state)
        logger.debug(f"[AI] State persisted to Redis for match {match_id}")

        # STEP 4: Persist response to database (permanent record)
        db = SessionLocal()
        turn = APMatchRepository.create_turn(
            db=db,
            session_id=match_id,
            turn_number=state.current_turn_index,
            speaker_role=speaker_role,
            speaker_type=SpeakerType.AI.value,
            transcript_text=response,
            duration_seconds=0  # Will be updated if we have timing data
        )
        logger.info(f"[AI] Turn record created in database: {turn.id}")

        db.commit()   # Makes the turn record permanent in the database
        logger.debug(f"[AI] Turn record committed to database: {turn.id}")

        # CRITICAL: Advance the turn index so the debate continues.
        # (For human turns, the Go gateway does this when END_TURN is clicked.
        #  For AI turns, Python must do it here after generation is complete.)
        state.current_turn_index += 1
        await state_manager.update_state(state)
        logger.info(
            f"[AI] Turn advanced to index {state.current_turn_index} "
            f"(of {len(state.schedule)} total turns)"
        )

        # Publish TURN_CHANGED so redis_consumer decides who speaks next
        await client.publish(channel, json.dumps({
            "action": "TURN_CHANGED",
        }))
        logger.info(f"[AI] Published TURN_CHANGED to {channel}")

        return response

    except Exception as e:
        logger.exception(f"[AI] Error in generate_ai_response: {e}")
        error_event = {
            "event": "AI_ERROR",
            "error_message": f"Failed to generate response: {str(e)}"
        }
        await client.publish(channel, json.dumps(error_event))
        return None

    finally:
        if db:
            db.close()


async def persist_human_turn(
    client: redis.Redis,
    match_id: str,
    state: object
) -> bool:
    """
    Persist human speech to database when turn ends.

    Called when TURN_CHANGED is received and previous speaker was human.
    Go Gateway has already:
    1. Buffered all HUMAN_TRANSCRIPT_CHUNK events from Deepgram
    2. Combined them into final text
    3. Stored in Redis at debate:{match_id}:human_transcript:{turn_idx}
    4. Updated Redis Scoreboard with new current_turn_index
    5. Published TURN_CHANGED

    Python's job here:
    1. Retrieve final human transcript from Redis
    2. Create Turn record in Supabase (permanent storage)
    3. Add to transcript array in Redis state
    4. Clean up temporary Redis key

    Args:
        client: Redis async client
        match_id: Unique match identifier
        state: LiveMatchState object (current_turn_index already advanced by Go)

    Returns:
        bool: True if successfully persisted, False on error

    Example:
        >>> success = await persist_human_turn(redis_client, "match-123", state)
        >>> if success:
        ...     logger.info("Human speech saved!")
    """
    db = None
    try:
        if state.current_turn_index == 0:
            logger.debug(
                f"[HUMAN] No previous turn for match {match_id} (first turn)"
            )
            return True

        # Get the PREVIOUS speaker (human who just finished)
        previous_turn_index = state.current_turn_index - 1
        if previous_turn_index >= len(state.schedule):
            logger.warning(
                f"[HUMAN] Previous turn index {previous_turn_index} out of bounds "
                f"for match {match_id}"
            )
            return False

        previous_speaker = state.schedule[previous_turn_index]

        # RETRIEVE: Get human transcript from Redis
        # Go stored final combined text here
        human_transcript_key = (
            f"debate:{match_id}:human_transcript:{previous_turn_index}"
        )
        human_text = await client.get(human_transcript_key)

        if not human_text:
            logger.warning(
                f"[HUMAN] No transcript found in Redis key: {human_transcript_key}"
            )
            return False

        logger.info(
            f"[HUMAN] Retrieved human transcript ({len(human_text)} chars) "
            f"for {previous_speaker.role}"
        )

        # PERSIST: Save to Supabase database (ONE write per turn)
        db = SessionLocal()
        turn = APMatchRepository.create_turn(
            db=db,
            session_id=match_id,
            turn_number=previous_turn_index,
            speaker_role=previous_speaker.role,
            speaker_type=SpeakerType.HUMAN.value,
            transcript_text=human_text,
            duration_seconds=0  # Can be updated by Go if timing data available
        )
        logger.info(
            f"[HUMAN] Created turn record in Supabase: {turn.id} "
            f"({previous_speaker.role})"
        )

        db.commit()
        logger.debug(f"[HUMAN] Committed to database: {turn.id}")

        # STATE: Update transcript array in Redis state
        # Add to in-memory state so full transcript is available
        if not hasattr(state, 'transcript'):
            state.transcript = []

        state.transcript.append({
            "speaker_role": previous_speaker.role,
            "speaker_side": previous_speaker.side,
            "content": human_text,
            "player_type": "human"
        })

        # Update Redis state
        await state_manager.update_state(state)
        logger.debug(
            f"[HUMAN] Updated Redis state. Total turns in transcript: "
            f"{len(state.transcript)}"
        )

        # CLEANUP: Remove temporary Redis key
        await client.delete(human_transcript_key)
        logger.debug(f"[HUMAN] Cleaned up Redis key: {human_transcript_key}")

        return True

    except Exception as e:
        logger.exception(
            f"[HUMAN] Error persisting human turn for match {match_id}: {e}"
        )
        return False

    finally:
        if db:
            db.close()


# async def handle_poi_response(
#     client: redis.Redis,
#     match_id: str,
#     chunk: str
# ) -> None:
#     """
#     Handle Point of Order (POI) response generation.

#     Called when HUMAN_TRANSCRIPT_CHUNK is received and contains POI trigger words.
#     This is REAL-TIME, word-by-word POI analysis for future implementation.

#     Current flow:
#     1. Human is speaking (Deepgram streaming chunks)
#     2. Chunk contains POI keywords ("point of order", "raise a concern", etc.)
#     3. Detect POI and trigger response generation
#     4. Generate POI response and publish back to React
#     5. Continue listening for more chunks

#     Args:
#         client: Redis async client
#         match_id: Unique match identifier
#         chunk: The transcript chunk that triggered POI

#     Note:
#         This is called asynchronously via asyncio.create_task()
#         so it doesn't block the main consumer loop.

#     Example:
#         >>> if "point of order" in chunk.lower():
#         ...     asyncio.create_task(
#         ...         handle_poi_response(redis_client, match_id, chunk)
#         ...     )
#     """
#     try:
#         logger.info(f"[POI] 🚨 Processing POI for match {match_id}")
#         logger.debug(f"[POI] Chunk: {chunk}")

#         # ============================================================
#         # TODO: Implement POI logic
#         # ============================================================
#         # Future implementation:
#         # 1. Extract POI context from recent transcript
#         # 2. Generate POI response using LLM
#         # 3. Convert response to speech (ElevenLabs)
#         # 4. Publish audio to React via WebSocket
#         # 5. Log POI in database for analytics

#         # For now, just log it
#         logger.info(f"[POI] POI detected: {chunk}")

#         # Placeholder: Publish POI event to Redis
#         await client.publish(
#             f"debate:{match_id}:turns",
#             json.dumps({
#                 "event": "POI_DETECTED",
#                 "chunk": chunk,
#                 "message": "POI response will be generated here"
#             })
#         )

#     except Exception as e:
#         logger.exception(f"[POI] Error handling POI for match {match_id}: {e}")
