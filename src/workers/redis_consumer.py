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
    # Pattern: debate:{match_id}:* catches all events (aligned with Go's channel naming)
    await pubsub.psubscribe("debate:*")
    print("Python AI Worker is actively listening to all debate events (debate:*)...")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]

            # Extract match_id from channel format: "debate:{match_id}:turns"
            # Go publishes to: "debate:{match_id}:turns"
            # We split on ":" and take [1] as the match_id
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
                    # Go just patched current_turn_index directly in Redis state ("match_state:{id}")
                    # and published this event as a notification signal (no data payload).
                    # We read the FULL updated state from Redis — Go already incremented the index there.
                    # This aligns with Go's IncrementTurn() pattern (map[string]interface{} patch).
                    print(f"TURN_CHANGED received for match {match_id}")

                    # Read the FULL state from Redis that Go just patched
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
                        asyncio.create_task(trigger_adjudication(client, channel, match_id, state))
                        await client.publish(channel, json.dumps({
                            "event": "MATCH_COMPLETE",
                            "message": "All speeches delivered. Adjudication starting..."
                        }))
                        continue

                    # Debate still going — check who speaks next based on current_turn_index
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

                elif action == "POI_OFFERED":
                    # Human clicked "Offer POI" while the AI is speaking.
                    # Forward to the Sniper agent to decide accept/decline.
                    poi_text = data.get("text", "")
                    elapsed_seconds = data.get("elapsed_seconds", 150)

                    if not poi_text:
                        print("[WARN] POI_OFFERED received with no text. Ignoring.")
                        continue

                    state = await state_manager.get_state(match_id)
                    if not state:
                        continue

                    # Only handle if it is actually the AI's turn (defensive check)
                    current_turn = state.schedule[state.current_turn_index]
                    if current_turn.player_type == "ai":
                        print(f"Human offered POI: '{poi_text[:50]}...' at {elapsed_seconds}s")
                        asyncio.create_task(
                            handle_poi_to_ai(
                                client=client,
                                channel=channel,
                                match_id=match_id,
                                state=state,
                                poi_text=poi_text,
                                elapsed_seconds=elapsed_seconds,
                            )
                        )
                    else:
                        print("[WARN] POI_OFFERED received but it is not AI's turn. Ignoring.")

                else:
                    print(f"[INFO] Unknown action '{action}' on {channel}. Ignoring.")

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
        channel: Redis pub/sub channel (e.g., "debate:{match_id}:turns")
        match_id: Unique match identifier
        state: LiveMatchState object from state_manager
    """
    db = None
    try:
        # Get current speaker info from schedule
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
            session_id=match_id
        )

        print(f"AI Response generated ({len(response)} chars): {response[:100]}...")

        # Persist the generated response back to state
        turn_data = {
            "speaker_role": speaker_role,
            "content": response
        }
        state.transcript.append(turn_data)
        print(f"Appended {speaker_role} response to transcript. Total turns: {len(state.transcript)}")

        # Save updated state back to Redis
        await state_manager.update_state(state)
        print(f"State persisted to Redis for match {match_id}")

        # Save turn to Supabase for permanent storage
        db = SessionLocal()
        turn = create_turn(
            db=db,
            session_id=match_id,
            turn_number=state.current_turn_index,
            speaker_role=speaker_role,
            speaker_type="AI",
            transcript_text=response,
            duration_seconds=0
        )
        print(f"Turn record created in Supabase: {turn.id}")
        db.commit()
        print(f"Turn record committed to Supabase: {turn.id}")

    except Exception as e:
        print(f"Error in generate_ai_response: {e}")
        await client.publish(channel, json.dumps({
            "event": "AI_ERROR",
            "error_message": f"Failed to generate response: {str(e)}"
        }))
    finally:
        if db:
            db.close()


def reconstruct_transcript(state: object) -> str:
    """
    Reconstruct debate transcript from state history.

    Concatenates all previous turns with speaker role and content.

    Args:
        state: LiveMatchState object

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


async def handle_poi_to_ai(
    client,
    channel: str,
    match_id: str,
    state,
    poi_text: str,
    elapsed_seconds: int,
):
    """
    Feature 1: Human offers a POI while the AI is speaking.

    Flow:
    1. Call SniperAgent to get accept/decline decision
    2. Record the POI event in Python's state
    3. Publish the outcome (POI_ACCEPTED or POI_DECLINED) to Redis
    4. Go receives it and forwards to React frontend

    The state update ensures the Adjudicator (Step 4) can see all POI history.
    """
    from src.ai.agents.sniper import SniperAgent
    from src.schemas.state_schema import POIRecord

    sniper = SniperAgent()
    current_turn = state.schedule[state.current_turn_index]

    # Ask Sniper to decide — hard rules first, LLM for nuanced cases
    result = await sniper.evaluate_incoming_poi(
        poi_text=poi_text,
        our_role=current_turn.role,
        our_side=current_turn.side,
        elapsed_seconds=elapsed_seconds,
        speech_so_far="",  # TODO: store live speech content in state
        pois_accepted_count=state.total_pois_accepted_by_ai,
        format_type="ap",  # TODO: store format_type in LiveMatchState
    )

    # Build a record of this POI for the adjudicator
    poi_record = POIRecord(
        offered_by="human",
        poi_text=poi_text,
        outcome=result["decision"],
        response_text=result.get("response_text"),
        offered_at_second=elapsed_seconds,
    )

    # Update state: add to both current-turn list and full match history
    state.pois_this_turn.append(poi_record)
    state.all_pois.append(poi_record)

    if result["decision"] == "accept":
        state.total_pois_accepted_by_ai += 1
        await state_manager.update_state(state)
        print(f"[Sniper] POI ACCEPTED. Response: {result['response_text'][:60]}")
        await client.publish(channel, json.dumps({
            "event": "POI_ACCEPTED",
            "response": result["response_text"],
        }))
    else:
        await state_manager.update_state(state)
        print(f"[Sniper] POI DECLINED. Response: {result['response_text']}")
        await client.publish(channel, json.dumps({
            "event": "POI_DECLINED",
            "response": result["response_text"],
        }))


async def trigger_adjudication(client, channel: str, match_id: str, state):
    """
    Called when all turns are complete (state.current_turn_index >= len(state.schedule)).
    Runs the full adjudication pipeline and publishes MATCH_COMPLETE to the channel.

    Flow:
    1. Fetch session details from DB (motion text, human role, user ID)
    2. Call grading_service.run_adjudication()
    3. Publish MATCH_COMPLETE event with summary scores
    """
    from src.services.grading_service import run_adjudication
    from src.models.debate import DebateSession

    db = SessionLocal()
    try:
        # Fetch the DebateSession to get motion, format, user details
        session = db.query(DebateSession).filter(
            DebateSession.id == match_id
        ).first()

        if not session:
            print(f"[Adjudication] ERROR: Session {match_id} not found in DB.")
            return

        # Run the full adjudication pipeline
        verdict = await run_adjudication(
            db=db,
            state=state,
            session_id=match_id,
            user_id=str(session.user_id),
            motion_text=session.motion.motion_text,
            format_type=session.format.value,
            human_speaker_role=session.human_role,
        )

        # Notify frontend: match is complete with summary scores
        await client.publish(channel, json.dumps({
            "event": "MATCH_COMPLETE",
            "winning_team": verdict["winning_team"],
            "gov_total_score": verdict["gov_total_score"],
            "opp_total_score": verdict["opp_total_score"],
            "overall_analysis": verdict.get("overall_analysis", ""),
        }))

        print(f"[Adjudication] Complete. Winner: {verdict['winning_team']}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Adjudication] ERROR: {e}")
        await client.publish(channel, json.dumps({
            "event": "ADJUDICATION_FAILED",
            "error": str(e),
        }))
    finally:
        db.close()
