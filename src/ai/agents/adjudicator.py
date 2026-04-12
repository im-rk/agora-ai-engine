"""
Adjudicator Agent — Post-Debate Scoring

Triggered when all turns complete. 
Input:  LiveMatchState (full transcript + POI history)
Output: Structured verdict dict (saved to adjudication_results + user_performance tables)

Uses GPT-4o-mini instead of Groq for this step because:
- The output schema is deeply nested (speaker array, clash table, etc.)
- GPT-4o-mini follows complex JSON schemas more reliably
- At low temperature, it produces more consistent calibrated scores
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage

from src.ai.clients.openai_client import get_openai_client
from src.ai.prompts.adjudicator_prompts import ADJUDICATOR_SCORING_PROMPT
from src.schemas.state_schema import LiveMatchState


class AdjudicatorAgent:
    """
    Reads the complete match state and produces a structured scoring verdict.

    The agent itself is stateless — all input comes from LiveMatchState.
    Post-processing (recalculate totals, determine winner) is done in Python,
    not trusted to the LLM, because LLMs are unreliable at arithmetic.
    """

    async def adjudicate(
        self,
        state: LiveMatchState,
        motion_text: str,
        format_type: str,
    ) -> dict:
        """
        Run the full adjudication pipeline.

        Args:
            state: The final LiveMatchState after all turns complete.
                   Must have .transcript and .all_pois populated.
            motion_text: The debate motion (e.g., "This house believes AI is good")
            format_type: "ap" or "bp"

        Returns:
            Verdict dict with speaker_scores, clash_table, winning_team, etc.
            The dict is ready to be passed directly to save_adjudication_result().
        """
        full_transcript = self._format_transcript(state.transcript)
        poi_summary = self._format_poi_summary(state)

        # GPT-4o-mini: best for structured output with complex nested JSON
        # Temperature 0.2: analytical, consistent, not creative
        llm = get_openai_client(model="gpt-4o-mini", temperature=0.2)

        messages = [
            SystemMessage(
                content=ADJUDICATOR_SCORING_PROMPT.format(
                    motion_text=motion_text,
                    format_type=format_type.upper(),
                    full_transcript=full_transcript,
                    poi_summary=poi_summary,
                )
            ),
            HumanMessage(content="Please adjudicate this debate. Be strict but fair."),
        ]

        print(f"[Adjudicator] Sending {len(full_transcript)} chars of transcript to GPT-4o-mini...")
        response = await llm.ainvoke(messages)

        # Parse JSON — handle cases where LLM wraps in markdown code blocks
        content = response.content.strip()
        if content.startswith("```"):
            # Strip markdown code block wrapping
            lines = content.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            content = "\n".join(lines).strip()

        verdict = json.loads(content)

        # Recalculate math in Python — never trust LLM arithmetic
        verdict = self._recalculate_totals(verdict)

        print(f"[Adjudicator] Done. Winner: {verdict['winning_team']} "
              f"(Gov: {verdict['gov_total_score']}, Opp: {verdict['opp_total_score']})")

        return verdict

    def _format_transcript(self, transcript: list) -> str:
        """Format the transcript list into a readable string for the prompt."""
        if not transcript:
            return "No speeches recorded."

        lines = []
        for i, turn in enumerate(transcript, 1):
            role = turn.get("speaker_role", "Unknown Speaker")
            content = turn.get("content", "(no content)")
            lines.append(f"[Turn {i}] {role}:\n{content}")

        return "\n\n".join(lines)

    def _format_poi_summary(self, state: LiveMatchState) -> str:
        """Format the POI history into a readable summary for the prompt."""
        if not state.all_pois:
            return "No Points of Information were exchanged in this debate."

        lines = [
            f"Total POIs accepted by AI: {state.total_pois_accepted_by_ai}",
            f"Total POIs accepted by Human: {state.total_pois_accepted_by_human}",
            "",
            "POI Events:",
        ]
        for p in state.all_pois:
            lines.append(
                f"  [{p.offered_at_second}s] {p.offered_by.upper()} offered: \"{p.poi_text}\""
                f" → {p.outcome.upper()}"
                + (f" | Response: \"{p.response_text}\"" if p.response_text else "")
            )

        return "\n".join(lines)

    def _recalculate_totals(self, verdict: dict) -> dict:
        """
        Recalculate all totals after receiving LLM output.

        WHY: LLMs are unreliable at arithmetic, especially across multiple entries.
        We calculate totals ourselves from the sub-scores.
        The LLM is instructed to leave total_score, gov_total_score, opp_total_score as 0.
        """
        gov_total = 0
        opp_total = 0

        for speaker in verdict.get("speaker_scores", []):
            total = (
                speaker.get("content_score", 0)
                + speaker.get("strategy_score", 0)
                + speaker.get("style_score", 0)
                + speaker.get("structure_score", 0)
                + speaker.get("poi_score", 0)
            )
            speaker["total_score"] = total

            side = speaker.get("speaker_side", "").lower()
            if "gov" in side:
                gov_total += total
            else:
                opp_total += total

        verdict["gov_total_score"] = gov_total
        verdict["opp_total_score"] = opp_total
        verdict["winning_team"] = "Government" if gov_total >= opp_total else "Opposition"

        return verdict
