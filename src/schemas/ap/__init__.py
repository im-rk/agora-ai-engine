"""
Asian Parliamentary (AP) Debate Schemas.

This package contains all request/response schemas for the AP debate format.
Organized by feature:
- matches.py: Match creation, listing, management schemas
- debates.py: Speech recording, debate state schemas (future)
- case_prep.py: Case prep coaching schemas (future)
- judging.py: Judging criteria and submission schemas (future)
- statistics.py: Statistics and analytics schemas (future)
"""

from .matches import (
    # Enums
    MatchStatus,
    APRole,
    DebateSide,
    # Request models
    CreateMatchRequest,
    UpdateMatchStatusRequest,
    ParticipantInfo,
    APMatchConfig,
    # Response models
    SpeakerInfo,
    TeamInfo,
    NextSpeaker,
    MatchResponse,
    MatchListItem,
    MatchListResponse,
)

__all__ = [
    # Enums
    "MatchStatus",
    "APRole",
    "DebateSide",
    # Request models
    "CreateMatchRequest",
    "UpdateMatchStatusRequest",
    "ParticipantInfo",
    "APMatchConfig",
    # Response models
    "SpeakerInfo",
    "TeamInfo",
    "NextSpeaker",
    "MatchResponse",
    "MatchListItem",
    "MatchListResponse",
]
