import asyncio
import json
import redis.asyncio as redis
from src.core.config import settings
from src.engine.state import state_manager 

async def start_redis_consumer():
    """Background worker that listens for game events and triggers the AI."""
    redis_url = settings.REDIS_URL
    client = redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()

    # Listen to ALL match channels using a wildcard (*)
    await pubsub.psubscribe("channel_*")
    print("🎧 Python AI Worker is actively listening to all matches (channel_*)...")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            match_id = channel.replace("channel_", "")
            raw_data = message["data"]

            print(f"Python heard on {channel}: {raw_data}")

            try:
                data = json.loads(raw_data)
                action = data.get("action")
                
                if action == "START_MATCH":
                    print(f"Match {match_id} Kickoff! Checking who goes first...")
                    state = await state_manager.get_state(match_id)
                    
                    if state and state.schedule[state.current_turn_index].player_type == "ai":
                        print("AI speaks first! Starting generation...")
                        asyncio.create_task(simulate_ai_thinking(client, channel))
                    else:
                        print("👤 Human speaks first. Python is going back to sleep.")
                
                elif action == "TURN_CHANGED":
                    print(f"Go updated the scoreboard for match {match_id}! Checking who is next...")
                    
                    # 1. READ ONLY! Do not advance the turn here.
                    state = await state_manager.get_state(match_id)
                    
                    if state and state.status != "finished":
                        # 2. Is the NEXT speaker an AI?
                        next_speaker = state.schedule[state.current_turn_index]
                        if next_speaker.player_type == "ai":
                            print(f"It is the {next_speaker.role}'s turn. AI waking up...")
                            asyncio.create_task(simulate_ai_thinking(client, channel))
                        else:
                            print(f"It is the {next_speaker.role}'s turn. Python going to sleep.")
                    else:
                        print(f"Match {match_id} is finished!")

            except json.JSONDecodeError:
                pass 
            except Exception as e:
                print(f"Python Consumer Error: {e}")

async def simulate_ai_thinking(redis_client, channel: str):
    """Fakes an LLM streaming words one by one."""
    fake_rebuttal = ["I", " completely", " disagree.", " Here", " is", " why."]
    
    for word in fake_rebuttal:
        await asyncio.sleep(0.5) 
        
        chunk_event = {
            "event": "AI_TOKEN",
            "text": word
        }
        await redis_client.publish(channel, json.dumps(chunk_event))
        print(f"Python streamed token: '{word}'")

    end_event = {"event": "AI_THOUGHT_COMPLETE"}
    await redis_client.publish(channel, json.dumps(end_event))
    print("Python finished thinking.")