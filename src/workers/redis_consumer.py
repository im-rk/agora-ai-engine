import asyncio
import json
import redis.asyncio as redis

from src.core.config import settings
from src.engine.state import state_manager
from src.schemas.event_schema import BaseEvent, EventType
from src.engine.rules import evaluate_rules

from src.ai.agents.debater import generate_ai_speech
from src.ai.agents.sniper import generate_poi
from src.ai.agents.adjudicator import adjudicate_match


async def start_redis_consumer():
    """Background worker that listens for game events and orchestrates the match."""

    redis_url = settings.REDIS_URL
    client = redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()

    await pubsub.psubscribe("channel_*")
    print(" Python AI Worker is actively listening to all matches (channel_*)...")

    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue

        channel = message["channel"]
        raw_data = message["data"]

        print(f" Python received on {channel}: {raw_data}")

        try:
            # -------------------------------
            # 1. Parse Event
            # -------------------------------
            event = BaseEvent.model_validate_json(raw_data)
            match_id = event.match_id
            payload = event.payload or {}

            # -------------------------------
            # 2. Get State
            # -------------------------------
            state = await state_manager.get_state(match_id)

            if not state:
                print(f" No state found for match {match_id}")
                continue

            # -------------------------------
            # 3. Handle USER INPUT
            # -------------------------------
            if event.type == EventType.USER_SPOKE:
                if "text" in payload:
                    state.transcript.append({
                        "speaker": "human",
                        "text": payload["text"]
                    })
                    await state_manager.update_state(state)

            # -------------------------------
            # 4. Handle AI COMPLETION → SNIPER
            # -------------------------------
            if event.type == EventType.AI_THOUGHT_COMPLETE:
                print(f" AI finished speaking → triggering sniper for {match_id}")
                asyncio.create_task(generate_poi(match_id))

            # -------------------------------
            # 5. Evaluate Rules
            # -------------------------------
            decision = evaluate_rules(event, state)

            # -------------------------------
            # 6. EXECUTION LAYER
            # -------------------------------

            #  Advance Turn

            if event.type == EventType.MATCH_ENDED:
                print(f"Adjudicating match {match_id}")
                asyncio.create_task(adjudicate_match(match_id))


            if decision.should_advance_turn:
                state.current_turn_index += 1
                await state_manager.update_state(state)

                next_event = {
                    "type": EventType.TURN_CHANGED,
                    "match_id": match_id,
                    "payload": {}
                }

                await client.publish(channel, json.dumps(next_event))
                print(f" Turn advanced for match {match_id}")

            #  Trigger AI
            if decision.should_ai_speak:
                print(f" AI turn triggered for match {match_id}")
                asyncio.create_task(generate_ai_speech(match_id))

            #  End Match (future)
            if decision.is_match_finished:
                end_event = {
                    "type": EventType.MATCH_ENDED,
                    "match_id": match_id,
                    "payload": {}
                }

                await client.publish(channel, json.dumps(end_event))
                print(f" Match ended for {match_id}")

        except json.JSONDecodeError:
            print(" Invalid JSON received")

        except Exception as e:
            print(f" Python Consumer Error: {e}")