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
from src.repositories.bp.matches import BPMatchRepository
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
    """
    db = None
    try:
        if not state.schedule or state.current_turn_index >= len(state.schedule):
            logger.error(
                f"Invalid state for match {match_id}: "
                f"schedule empty or index {state.current_turn_index} out of bounds"
            )
            return None

        current_speaker = state.schedule[state.current_turn_index]
        speaker_role = current_speaker.role 
        speaker_id = f"{match_id}:{state.current_turn_index}"
        speaker_side = current_speaker.side  
        
        db = SessionLocal()
        match_repository = APMatchRepository
        try:
            match_data = APMatchRepository.get_match_with_motion(db, match_id)
            if not match_data:
                match_data = BPMatchRepository.get_match_with_motion(db, match_id)
                match_repository = BPMatchRepository

            debate_session = match_data[0] if match_data else None
            motion_text = match_data[1].motion_text if match_data and match_data[1] else "The motion under debate"
            format_type = debate_session.format.value.lower() if debate_session else "ap"  # e.g., "BP" → "bp"
            skill_level = debate_session.skill_level.value if debate_session and debate_session.skill_level else "Beginner"
        except Exception as e:
            logger.error(f"Failed to fetch motion for match {match_id}: {e}")
            motion_text = "The motion under debate"
            format_type = "ap"  # Default to AP for backward compatibility
            skill_level = "Beginner"
            match_repository = APMatchRepository
        finally:
            db.close()

        transcript = reconstruct_transcript(state)

        logger.info(
            f"[AI] Starting 4-phase pipeline for {speaker_role} ({speaker_side}) "
            f"in {format_type.upper()} format (speaker_id: {speaker_id})"
        )
        logger.debug(f"[AI] Transcript length: {len(transcript)} chars")

        debater = DebaterAgent(format_type=format_type, redis_client=client)

        await client.publish(channel, json.dumps({
            "event": "TURN_STARTED",
            "speaker": "ai",
            "role": speaker_role,  
            "side": speaker_side,
            "turn_index": state.current_turn_index,
        }))
        logger.info(f"[AI] Published TURN_STARTED for {speaker_role} on {channel}")

        response = await debater.orchestrate_debater_response(
            transcript=transcript,
            motion=motion_text,
            speaker_role=speaker_role,  # Full AP role name
            speaker_id=speaker_id,
            speaker_side=speaker_side,
            difficulty_level=skill_level,
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
        turn = match_repository.create_turn(
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

       
        state.current_turn_index += 1
        await state_manager.update_state(state)
        logger.info(
            f"[AI] Turn advanced to index {state.current_turn_index} "
            f"(of {len(state.schedule)} total turns)"
        )

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

    Database Table: turns
    - session_id (match_id)
    - turn_number (sequence)
    - speaker_role (e.g., "Prime Minister")
    - speaker_type: "Human" (STORED HERE)
    - transcript_text: VOICE TRANSCRIPT (STORED HERE)
    - duration_seconds

    Args:
        client: Redis async client
        match_id: Unique match identifier
        state: LiveMatchState object (current_turn_index already advanced by Go)

    Returns:
        bool: True if successfully persisted, False on error
    """
    db = None
    try:
        logger.info(f"[HUMAN] Starting human turn persistence for match {match_id}")
        logger.debug(f"[HUMAN] Current turn index: {state.current_turn_index}")
        
        if state.current_turn_index == 0:
            logger.debug(
                f"[HUMAN] No previous turn for match {match_id} (first turn is current)"
            )
            return True

        previous_turn_index = state.current_turn_index - 1
        
        logger.debug(
            f"[HUMAN] Looking for previous speaker at index {previous_turn_index} "
            f"(schedule length: {len(state.schedule)})"
        )
        
        if previous_turn_index >= len(state.schedule):
            logger.warning(
                f"[HUMAN] Previous turn index {previous_turn_index} out of bounds "
                f"for match {match_id} (schedule length: {len(state.schedule)})"
            )
            return False

        previous_speaker = state.schedule[previous_turn_index]
        logger.info(
            f"[HUMAN] Previous speaker: {previous_speaker.role} "
            f"(player_type: {previous_speaker.player_type})"
        )

        human_transcript_key = (
            f"debate:{match_id}:human_transcript:{previous_turn_index}"
        )
        logger.debug(f"[HUMAN] Fetching transcript from Redis key: {human_transcript_key}")
        
        human_text = await client.get(human_transcript_key)

        if not human_text:
            logger.warning(
                f"[HUMAN] No transcript found in Redis: {human_transcript_key} "
                f"(Key may have expired or not been set by Go)"
            )
            return False

        logger.info(
            f"[HUMAN] Retrieved transcript ({len(human_text)} chars) for {previous_speaker.role}"
        )

        logger.debug(f"[HUMAN] Creating database session...")
        db = SessionLocal()
        
        logger.debug(
            f"[HUMAN] Saving turn to turns table:\n"
            f"  - session_id: {match_id}\n"
            f"  - turn_number: {previous_turn_index}\n"
            f"  - speaker_role: {previous_speaker.role}\n"
            f"  - speaker_type: Human\n"
            f"  - transcript_length: {len(human_text)} chars"
        )
        
        turn = APMatchRepository.create_turn(
            db=db,
            session_id=match_id,
            turn_number=previous_turn_index,
            speaker_role=previous_speaker.role,
            speaker_type=SpeakerType.HUMAN.value,  # "Human"
            transcript_text=human_text,  # VOICE TRANSCRIPT STORED HERE
            duration_seconds=0  # Can be updated by Go if timing data available
        )
        
        logger.info(
            f"[HUMAN] SAVED to turns table:\n"
            f"  - Turn ID: {turn.id}\n"
            f"  - Role: {previous_speaker.role}\n"
            f"  - Type: Human\n"
            f"  - Match: {match_id}"
        )

        db.commit()
        logger.debug(f"[HUMAN] Database committed: {turn.id}")

        logger.debug(f"[HUMAN] Updating Redis state transcript array...")
        
        if not hasattr(state, 'transcript'):
            state.transcript = []

        state.transcript.append({
            "speaker_role": previous_speaker.role,
            "speaker_side": previous_speaker.side,
            "content": human_text,
            "player_type": "human"
        })

        await state_manager.update_state(state)
        logger.info(
            f"[HUMAN] Updated Redis state: {len(state.transcript)} total turns in transcript"
        )

        logger.debug(f"[HUMAN] Cleaning up temporary Redis key...")
        deleted = await client.delete(human_transcript_key)
        logger.debug(f"[HUMAN] Cleaned up Redis key (deleted: {deleted})")

        logger.info(
            f"[HUMAN] HUMAN TURN PERSISTENCE COMPLETE\n"
            f"  - Stored in turns table (ID: {turn.id})\n"
            f"  - Updated Redis state\n"
            f"  - Cleaned up temporary keys"
        )
        return True

    except Exception as e:
        logger.error(
            f"[HUMAN] FAILED to persist human turn for match {match_id}"
        )
        logger.exception(f"[HUMAN] Exception details: {e}")
        if db:
            db.rollback()
        return False

    finally:
        if db:
            db.close()
            logger.debug(f"[HUMAN] Database session closed")


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
