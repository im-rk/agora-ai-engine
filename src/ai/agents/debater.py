from src.ai.prompts.debater_prompts import get_debater_prompt
from src.ai.clients.openai_client import get_openai_client
from src.ai.callbacks.redis_stream import RedisStreamingCallbackHandler

from src.engine.state import state_manager
from src.repositories.case_prep_repo import get_case_prep_by_match
from src.core.database import SessionLocal
from src.core.redis_client import redis_client


async def generate_ai_speech(match_id: str):
    """
    Debater Agent:
    Generates AI speech using:
    - transcript (context)
    - case prep (knowledge)
    - role (persona)
    """

    # -------------------------
    # 1. Get State
    # -------------------------
    state = await state_manager.get_state(match_id)
    if not state:
        return

    current_turn = state.schedule[state.current_turn_index]
    role = current_turn.role
    side = current_turn.side

    # -------------------------
    # 2. Get Case Prep
    # -------------------------
    db = SessionLocal()
    case_prep = get_case_prep_by_match(db, match_id)
    db.close()

    arguments = case_prep.arguments if case_prep else []
    counter_arguments = case_prep.counter_arguments if case_prep else []

    # -------------------------
    # 3. Build Transcript
    # -------------------------
    transcript = state.transcript[-10:]

    formatted_transcript = "\n".join([
        f"{t['speaker']}: {t['text']}" for t in transcript
    ])

    # -------------------------
    # 4. Build Prompt Chain
    # -------------------------
    prompt = get_debater_prompt()

    llm = get_openai_client(
        model="gpt-4o-mini",
        temperature=0.7
    )

    # -------------------------
    # 5. Streaming Callback
    # -------------------------
    channel = f"channel_{match_id}"
    callback = RedisStreamingCallbackHandler(redis_client, channel)

    chain = prompt | llm.bind(callbacks=[callback])

    # -------------------------
    # 6. Invoke LLM
    # -------------------------
    result = await chain.ainvoke({
        "transcript": formatted_transcript,
        "role": role,
        "side": side,
        "arguments": arguments,
        "counter_arguments": counter_arguments
    })

    full_text = result.content

    # -------------------------
    # 7. Save to State
    # -------------------------
    state.transcript.append({
        "speaker": "ai",
        "text": full_text
    })

    await state_manager.update_state(state)

    return full_text