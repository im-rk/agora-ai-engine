"""
Sniper Agent — Point of Information (POI) Handler

Two modes:

DEFENSIVE :
  The human offers a POI while the AI is speaking.
  The Sniper decides: accept or decline? Generates appropriate response.
  Used when: Redis consumer receives action="POI_OFFERED"

OFFENSIVE :
  The AI monitors the human's live transcript.
  The Sniper scans for weak arguments and decides whether to interrupt.
  Used when: Go fires a periodic HUMAN_TRANSCRIPT event with live STT text.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage

from src.ai.clients.groq_client import get_groq_client
from src.ai.prompts.sniper_prompts import (
    SNIPER_ACCEPT_DECLINE_PROMPT,
    SNIPER_OFFER_POI_PROMPT,
)
from src.engine.rules import get_rules, is_poi_window_open


class SniperAgent:
    """
    Handles all POI decision-making.

    Uses Groq (llama-3.1-8b-instant) at low temperature because this
    is a TACTICAL decision, not a creative one. We want consistent,
    rule-following behavior — not creativity.
    """

    async def evaluate_incoming_poi(
        self,
        poi_text: str,
        our_role: str,
        our_side: str,
        elapsed_seconds: int,
        speech_so_far: str,
        pois_accepted_count: int,
        format_type: str = "ap",
    ) -> dict:
        """
        DEFENSIVE MODE: Human offered us a POI while we are speaking.
        Decide whether to accept or decline. Generate the response.

        Hard rules are checked BEFORE calling the LLM to avoid unnecessary API costs.

        Args:
            poi_text: What the human is asking
            our_role: Our current speaker role (e.g., "Prime Minister")
            our_side: "Government" or "Opposition"
            elapsed_seconds: How far into our speech we are
            speech_so_far: The text of our speech up to this point
            pois_accepted_count: How many POIs we've already accepted this speech
            format_type: "ap" or "bp"

        Returns:
            dict with keys: "decision" ("accept"|"decline"), "response_text" (str)
        """
        rules = get_rules(format_type)

        # ── Hard Rule 1: Already at the acceptance limit ──
        # Don't even call the LLM. Save API costs, make instant decision.
        if pois_accepted_count >= rules.max_pois_to_accept_per_speech:
            print(f"[Sniper] Hard decline: already accepted {pois_accepted_count} POIs this speech.")
            return {
                "decision": "decline",
                "response_text": "Not at this time, thank you.",
            }

        # ── Hard Rule 2: POI window is closed ──
        if not is_poi_window_open(format_type, elapsed_seconds):
            print(f"[Sniper] Hard decline: POI window closed at {elapsed_seconds}s.")
            return {
                "decision": "decline",
                "response_text": "I'm afraid this is a protected period.",
            }

        # ── LLM Decision: nuanced cases ──
        # Low temperature (0.3) = precise, tactical, consistent
        llm = get_groq_client(streaming=False, temperature=0.3)

        messages = [
            SystemMessage(
                content=SNIPER_ACCEPT_DECLINE_PROMPT.format(
                    our_role=our_role,
                    our_side=our_side,
                    format_type=format_type.upper(),
                    elapsed_seconds=elapsed_seconds,
                    total_seconds=rules.speech_duration_seconds,
                    poi_text=poi_text,
                    # Only pass last 500 chars — the LLM doesn't need the full speech
                    speech_so_far=speech_so_far[-500:] if speech_so_far else "Speech just started.",
                    pois_accepted_count=pois_accepted_count,
                )
            ),
            HumanMessage(content="Make your POI decision now."),
        ]

        response = await llm.ainvoke(messages)

        try:
            result = json.loads(response.content)
            print(f"[Sniper] LLM decision: {result.get('decision')} — {result.get('response_text', '')[:60]}")
            return result
        except json.JSONDecodeError:
            # Fallback if LLM returns non-JSON (shouldn't happen, but be defensive)
            print(f"[Sniper] JSON parse failed. Defaulting to decline.")
            return {
                "decision": "decline",
                "response_text": "Not at this time, thank you.",
            }

    async def generate_ai_poi_question(
        self,
        human_transcript_so_far: str,
        our_side: str,
        our_role: str,
        our_arguments_summary: str,
    ) -> dict:
        """
        OFFENSIVE MODE: AI scans human's live transcript for a POI opportunity.
        Returns a POI question if a good opportunity exists, otherwise returns should_offer=False.

        NOTE: This is Feature 2. For MVP, Go can randomly trigger this instead of 
        calling it on every transcript chunk. See Step 3E for Go-side MVP approach.

        Args:
            human_transcript_so_far: Live STT transcript of human's speech (last 800 chars)
            our_side: "Government" or "Opposition"
            our_role: Our next speaker role
            our_arguments_summary: Summary of our prepared case

        Returns:
            dict with: "should_offer" (bool), "poi_text" (str|None), "target_claim" (str|None)
        """
        llm = get_groq_client(streaming=False, temperature=0.4)

        messages = [
            SystemMessage(
                content=SNIPER_OFFER_POI_PROMPT.format(
                    our_side=our_side,
                    our_role=our_role,
                    # Last 800 chars = relevant context without overwhelming the LLM
                    human_transcript_so_far=human_transcript_so_far[-800:],
                    our_arguments_summary=our_arguments_summary,
                )
            ),
            HumanMessage(content="Should we offer a POI right now?"),
        ]

        response = await llm.ainvoke(messages)

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"should_offer": False, "poi_text": None, "target_claim": None}
