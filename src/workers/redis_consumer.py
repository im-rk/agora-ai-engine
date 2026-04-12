import asyncio
import json
import redis.asyncio as redis
from src.core.config import settings
from src.core.database import SessionLocal
from src.engine.state import state_manager
from src.ai.agents.debater import DebaterAgent
from src.repositories.debate_repo import create_turn


async def start_redis_consumer():
    """Background worker that listens for game events and triggers the AI."""
    redis_url = settings.REDIS_URL
    client = redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()

    # Listen to ALL match events: turns, completions, errors, etc.
    # Pattern: debate:{match_id}:* catches all events
    await pubsub.psubscribe("debate:*")
    print("Python AI Worker is actively listening to all debate events (debate:*)...")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            # Extract match_id from channel format: "debate:{match_id}:turns"
            parts = channel.split(":")
            match_id = parts[1] if len(parts) > 1 else None
            if not match_id:
                continue
            raw_data = message["data"]

            print(f"Python heard on {channel}: {raw_data}")

            try:
                data = json.loads(raw_data)
                action = data.get("action")
                
                if action == "START_MATCH":
                    print(f"Match {match_id} Kickoff! Checking who goes first...")
                    state = await state_manager.get_state(match_id)
                    
                    if state and state.schedule[state.current_turn_index].player_type == "ai":
                        print("AI speaks first! Starting 4-phase debate pipeline...")
                        asyncio.create_task(
                            generate_ai_response(
                                client=client,
                                channel=channel,
                                match_id=match_id,
                                state=state
                            )
                        )
                    else:
                        print("Human speaks first. Python is going back to sleep.")
                
                elif action == "TURN_CHANGED":
                    # Go just incremented the turn in Redis state.
                    # Python reads the full state from Redis (Go already updated it).
                    print(f"TURN_CHANGED received for match {match_id}")

                    # Read the FULL state from Redis that Go just updated
                    state = await state_manager.get_state(match_id)

                    if not state:
                        print(f"[WARN] No Python state found for match {match_id}.")
                        continue
                    
                    print(f"Current turn index: {state.current_turn_index}")

                    # Has every turn been delivered? (index past end of schedule)
                    if state.current_turn_index >= len(state.schedule):
                        print(f"All turns complete for match {match_id}. Marking finished...")
                        state.status = "finished"
                        await state_manager.update_state(state)
                        # TODO Step 4: wire adjudication here
                        await client.publish(channel, json.dumps({
                            "event": "MATCH_COMPLETE",
                            "message": "All speeches delivered. Adjudication starting..."
                        }))
                        continue

                    # Check who speaks next based on current_turn_index
                    if state.current_turn_index < len(state.schedule):
                        next_speaker = state.schedule[state.current_turn_index]
                        if next_speaker.player_type == "ai":
                            print(f"It is the {next_speaker.role}'s turn (AI). Generating response...")
                            asyncio.create_task(
                                generate_ai_response(
                                    client=client,
                                    channel=channel,
                                    match_id=match_id,
                                    state=state
                                )
                            )
                        else:
                            print(f"It is the {next_speaker.role}'s turn (Human). Waiting for human speech...")
                    else:
                        print(f"[WARN] Turn index {state.current_turn_index} is beyond schedule length {len(state.schedule)}")

                else:
                    print(f"Match {match_id} is finished!")

            except json.JSONDecodeError:
                pass 
            except Exception as e:
                print(f"Python Consumer Error: {e}")


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
        channel: Redis channel (e.g., "channel_match123")
        match_id: Unique match identifier
        state: DebateState object from state_manager
    """
    db = None
    try:
        # Get current speaker info
        current_speaker = state.schedule[state.current_turn_index]
        speaker_role = current_speaker.role  
        speaker_id = f"{match_id}:{state.current_turn_index}"
        
        # Reconstruct debate transcript from state history
        transcript = reconstruct_transcript(state)
        
        print(f"Starting 4-phase pipeline for {speaker_role} (speaker_id: {speaker_id})")
        print(f"Transcript length: {len(transcript)} chars")
        
        # Initialize debater agent
        debater = DebaterAgent(redis_client=client)
        
        # Execute 4-phase orchestration (streaming to Redis)
        response = await debater.orchestrate_debater_response(
            transcript=transcript,
            speaker_role=speaker_role,
            speaker_id=speaker_id,
            personality_trait="balanced",
            session_id=match_id  # Pass session_id for logging all LLM calls
        )
        
        print(f"AI Response generated ({len(response)} chars): {response[:100]}...")
        
        # STEP 3: Persist the generated response back to state
        # Create turn object with speaker role and content
        turn_data = {
            "speaker_role": speaker_role,
            "content": response
        }
        
        # Append to transcript
        state.transcript.append(turn_data)
        print(f"Appended {speaker_role} response to transcript. Total turns: {len(state.transcript)}")
        
        # Save updated state back to Redis
        await state_manager.update_state(state)
        print(f"State persisted to Redis for match {match_id}")
        
        # STEP 4: Save turn to Supabase
        db = SessionLocal()
        turn = create_turn(
            db=db,
            session_id=match_id,
            turn_number=state.current_turn_index,
            speaker_role=speaker_role,
            speaker_type="AI",
            transcript_text=response,
            duration_seconds=0  # Will be updated if we have timing data
        )
        print(f"Turn record created in Supabase: {turn.id}")

        db.commit()   # Makes the turn record permanent in the database
        print(f"Turn record committed to Supabase: {turn.id}")

        
    except Exception as e:
        print(f"Error in generate_ai_response: {e}")
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
    
    Concatenates all previous turns with speaker role and content.
    
    Args:
        state: DebateState object
    
    Returns:
        Formatted debate transcript string
    """
    if not hasattr(state, 'transcript') or not state.transcript:
        return "Debate just started. No prior arguments."
    
    transcript_lines = []
    for turn in state.transcript:
        speaker_role = turn.get("speaker_role", "Unknown")
        content = turn.get("content", "")
        transcript_lines.append(f"{speaker_role}: {content}")
    
    return "\n\n".join(transcript_lines)
