"""
Asian Parliamentary (AP) Match Schemas.

Simple request/response models for 4 core operations:
1. CreateMatchRequest → MatchResponse (POST /matches)
2. UpdateMatchStatusRequest → MatchResponse (PATCH /matches/{id})
3. MatchListResponse (GET /matches)
4. MatchResponse (GET /matches/{id})

No complex team management - just motion, side, role.
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


class APRole(str, Enum):
    """AP debate roles (6 total)."""
    PRIME_MINISTER = "prime_minister"
    LEADER_OF_OPPOSITION = "leader_of_opposition"
    DEPUTY_PRIME_MINISTER = "deputy_prime_minister"
    DEPUTY_LEADER_OF_OPPOSITION = "deputy_leader_of_opposition"
    GOVERNMENT_WHIP = "government_whip"
    OPPOSITION_WHIP = "opposition_whip"


class DebateSide(str, Enum):
    """Debate sides."""
    GOVERNMENT = "government"
    OPPOSITION = "opposition"


# REQUEST MODELS

class CreateMatchRequest(BaseModel):
    """Create new AP match."""
    motion: str = Field(..., min_length=10, max_length=500, description="Debate motion")
    side: DebateSide = Field(..., description="government | opposition")
    role: APRole = Field(..., description="Your AP role")


class UpdateMatchStatusRequest(BaseModel):
    """Update match status."""
    status: MatchStatus = Field(..., description="New status")



# RESPONSE MODELS

class ParticipantInfo(BaseModel):
    """Participant in match."""
    user_id: str
    role: APRole
    side: DebateSide
    status: str = "JOINED"


class MatchResponse(BaseModel):
    """Match details response for GET, POST, PATCH."""
    match_id: str = Field(..., description="Match UUID")
    motion: str = Field(..., description="Debate motion")
    status: MatchStatus = Field(..., description="Match status")
    created_by: str = Field(..., description="User who created match")
    your_role: APRole = Field(..., description="Your role in this match")
    your_side: DebateSide = Field(..., description="Your side")
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
    your_role: APRole = Field(..., description="Your role")
    your_side: DebateSide = Field(..., description="Your side")
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MatchListResponse(BaseModel):
    """Paginated list of user's matches."""
    matches: List[MatchListItem] = Field(default_factory=list)
    total: int = Field(..., description="Total matches")
    skip: int = Field(..., description="Pagination offset")
    limit: int = Field(..., description="Page size")
