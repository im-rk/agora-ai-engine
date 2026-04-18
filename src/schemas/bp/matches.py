"""
British Parliamentary (BP) Match Schemas.

Simple request/response models for 4 core operations:
1. CreateMatchRequest → MatchResponse (POST /matches)
2. UpdateMatchStatusRequest → MatchResponse (PATCH /matches/{id})
3. MatchListResponse (GET /matches)
4. MatchResponse (GET /matches/{id})

BP has 8 speakers across 4 teams:
- Opening Government (OG): Prime Minister + Deputy Prime Minister
- Opening Opposition (OO): Leader of Opposition + Deputy Leader of Opposition
- Closing Government (CG): Member of Government + Government Whip
- Closing Opposition (CO): Member of Opposition + Opposition Whip

Go Gateway orchestrates all state transitions.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ENUMS

class MatchStatus(str, Enum):
    """Match lifecycle states."""
    AWAITING_PARTICIPANTS = "awaiting_participants"
    DEBATE_IN_PROGRESS = "debate_in_progress"
    JUDGING_PHASE = "judging_phase"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BPRole(str, Enum):
    """BP debate roles (8 total — 2 more than AP)."""
    PRIME_MINISTER = "prime_minister"
    LEADER_OF_OPPOSITION = "leader_of_opposition"
    DEPUTY_PRIME_MINISTER = "deputy_prime_minister"
    DEPUTY_LEADER_OF_OPPOSITION = "deputy_leader_of_opposition"
    MEMBER_OF_GOVERNMENT = "member_of_government"           # BP-only
    MEMBER_OF_OPPOSITION = "member_of_opposition"           # BP-only
    GOVERNMENT_WHIP = "government_whip"
    OPPOSITION_WHIP = "opposition_whip"


class BPTeam(str, Enum):
    """BP debate teams (4 teams — AP only has 2 sides)."""
    OPENING_GOVERNMENT = "opening_government"    # OG: PM + DPM
    OPENING_OPPOSITION = "opening_opposition"    # OO: LO + DLO
    CLOSING_GOVERNMENT = "closing_government"    # CG: MG + GW
    CLOSING_OPPOSITION = "closing_opposition"    # CO: MO + OW


# REQUEST MODELS

class CreateMatchRequest(BaseModel):
    """Create new BP match."""
    motion: str = Field(..., min_length=10, max_length=500, description="Debate motion")
    team: BPTeam = Field(..., description="Your team (OG, OO, CG, CO)")
    role: BPRole = Field(..., description="Your BP role")


class UpdateMatchStatusRequest(BaseModel):
    """Update match status."""
    status: MatchStatus = Field(..., description="New status")
    reason: Optional[str] = Field(None, description="Reason for status change")



# RESPONSE MODELS

class ParticipantInfo(BaseModel):
    """Participant in match."""
    user_id: str
    role: BPRole
    team: BPTeam
    status: str = "JOINED"


class MatchResponse(BaseModel):
    """Match details response for GET, POST, PATCH."""
    match_id: str = Field(..., description="Match UUID")
    motion: str = Field(..., description="Debate motion")
    status: MatchStatus = Field(..., description="Match status")
    created_by: str = Field(..., description="User who created match")
    your_role: BPRole = Field(..., description="Your role in this match")
    your_team: BPTeam = Field(..., description="Your team")
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    participants: List[ParticipantInfo] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class MatchListItem(BaseModel):
    """Match info for list view."""
    id: str = Field(..., description="Match UUID")
    motion: str = Field(..., description="Debate motion")
    status: MatchStatus = Field(..., description="Match status")
    your_role: BPRole = Field(..., description="Your role")
    your_team: BPTeam = Field(..., description="Your team")
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MatchListResponse(BaseModel):
    """Paginated list of user's matches."""
    matches: List[MatchListItem] = Field(default_factory=list)
    total: int = Field(..., description="Total matches")
    skip: int = Field(..., description="Pagination offset")
    limit: int = Field(..., description="Page size")


# TYPE ALIAS FOR SERVICE RETURNS
MatchListResponseDict = dict  # {"matches": [...], "total": int, "skip": int, "limit": int}