"""
Transcript handling utilities for debate sessions.

This module provides functions to reconstruct and format debate transcripts
from state history for use in AI agent context generation.
"""

import logging

logger = logging.getLogger(__name__)


def reconstruct_transcript(state: object) -> str:
    """
    Reconstruct debate transcript from state history.

    Concatenates all previous turns with speaker role, side, and content.
    Used to provide context to DebaterAgent for response generation.

    Args:
        state: LiveMatchState object containing transcript history

    Returns:
        str: Formatted debate transcript with speaker roles and sides

    Example:
        >>> transcript = reconstruct_transcript(state)
        >>> print(transcript)
        "PMO (Affirmative): Opening arguments...\\n\\nLO (Negative): Rebuttal..."
    """
    if not hasattr(state, 'transcript') or not state.transcript:
        return "Debate just started. This is the opening speech."

    transcript_lines = []
    for turn in state.transcript:
        speaker_role = turn.get("speaker_role", "Unknown")
        speaker_side = turn.get("speaker_side", "")
        content = turn.get("content", "")

        # Format: "ROLE (SIDE): content"
        if speaker_side:
            header = f"{speaker_role} ({speaker_side}): {content}"
        else:
            header = f"{speaker_role}: {content}"

        transcript_lines.append(header)

    return "\n\n".join(transcript_lines)
