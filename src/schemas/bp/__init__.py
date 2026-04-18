"""
British Parliamentary (BP) Debate Schemas.

This package contains all request/response schemas for the BP debate format.
Organized by feature:
- matches.py: Match creation, listing, management schemas
- case_prep.py: Case prep generation schemas
- debates.py: Speech recording, debate state schemas (future)
- judging.py: Judging criteria and submission schemas (future)
- statistics.py: Statistics and analytics schemas (future)
"""

from .matches import (
    # Enums
    MatchStatus,
    BPRole,
    BPTeam,
    # Request models
    CreateMatchRequest,
    UpdateMatchStatusRequest,
    ParticipantInfo,
    # Response models
    MatchResponse,
    MatchListItem,
    MatchListResponse,
)

from .case_prep import (
    # Request models
    GenerateCasePrepRequest,
    # Response models
    Argument,
    CasePrepResponse,
)

__all__ = [
    # Enums (from matches)
    "MatchStatus",
    "BPRole",
    "BPTeam",
    # Request models (from matches)
    "CreateMatchRequest",
    "UpdateMatchStatusRequest",
    "ParticipantInfo",
    # Response models (from matches)
    "MatchResponse",
    "MatchListItem",
    "MatchListResponse",
    # Request models (from case_prep)
    "GenerateCasePrepRequest",
    # Response models (from case_prep)
    "Argument",
    "CasePrepResponse",
]