from src.ai.prompts.sniper_prompts import get_sniper_prompt
from src.ai.clients.openai_client import get_openai_client
from src.ai.callbacks.redis_stream import RedisStreamingCallbackHandler

from src.engine.state import state_manager
from src.core.redis_client import redis_client
import json

async def generate_poi(match_id: str):
    """
    Sniper Agent:
    Generates a Point of Information (POI)
    during opponent speech.
    """

    # -------------------------
    # 1. Get State
    # -------------------------
    state = await state_manager.get_state(match_id)
    if not state or not state.transcript:
        return

    # -------------------------
    # 2. Get Latest Speech
    # -------------------------
    latest_entry = state.transcript[-1]
    latest_speech = latest_entry["text"]

    # -------------------------
    # 3. Build Context
    # -------------------------
    transcript = state.transcript[-10:]

    formatted_transcript = "\n".join([
        f"{t['speaker']}: {t['text']}" for t in transcript
    ])

    # -------------------------
    # 4. Prompt + LLM
    # -------------------------
    prompt = get_sniper_prompt()

    llm = get_openai_client(
        model="gpt-4o-mini",
        temperature=0.5   # lower → sharper, less rambling
    )

    # -------------------------
    # 5. Streaming
    # -------------------------
    channel = f"channel_{match_id}"
    callback = RedisStreamingCallbackHandler(redis_client, channel)

    chain = prompt | llm.bind(callbacks=[callback])

    # -------------------------
    # 6. Generate POI
    # -------------------------
    result = await chain.ainvoke({
        "latest_speech": latest_speech,
        "transcript": formatted_transcript
    })

    poi_text = result.content

    # -------------------------
    # 7. Emit POI EVENT (IMPORTANT)
    # -------------------------
    poi_event = {
        "type": "POI_GENERATED",
        "match_id": match_id,
        "payload": {
            "text": poi_text
        }
    }

    await redis_client.publish(channel, json.dumps(poi_event))

    return poi_text