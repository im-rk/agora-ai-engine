"""
Asian Parliamentary (AP) Match Schemas.

Comprehensive request and response models for all match-related endpoints:
- POST   /api/v1/ap/matches              → CreateMatchRequest
- GET    /api/v1/ap/matches              → MatchListResponse
- GET    /api/v1/ap/matches/{id}         → MatchResponse
- PATCH  /api/v1/ap/matches/{id}         → UpdateMatchStatusRequest
- DELETE /api/v1/ap/matches/{id}         → MatchResponse (deleted match info)

AP Format Specifics:
- Speakers per side: 3 (first_speaker, second_speaker, whip)
- Total speeches: 6 (alternating government/opposition)
- Max speech time: 5 minutes (300 seconds)
- Judging criteria: Content (40%), Delivery (30%), Impact (30%)
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Literal, Dict
from datetime import datetime
from enum import Enum
from uuid import UUID


# ============================================================================
# ENUMS - Format-specific constants
# ============================================================================

class MatchStatus(str, Enum):
    """Match lifecycle states."""
    PENDING = "pending"              # Waiting for all participants to join
    IN_PROGRESS = "in_progress"      # Debate is currently happening
    COMPLETED = "completed"          # All 6 speeches done, judging submitted
    CANCELLED = "cancelled"          # Match was cancelled


class APRole(str, Enum):
    """AP debate roles (3 per side)."""
    FIRST_SPEAKER = "first_speaker"
    SECOND_SPEAKER = "second_speaker"
    WHIP = "whip"


class DebateSide(str, Enum):
    """Debate team sides."""
    GOVERNMENT = "government"
    OPPOSITION = "opposition"


# ============================================================================
# REQUEST MODELS - What frontend/client sends
# ============================================================================

class ParticipantInfo(BaseModel):
    """
    Information about a debate participant.
    
    Attributes:
        user_id (str): UUID of the participant
        role (APRole): Their role in debate (first_speaker, second_speaker, whip)
    """
    user_id: str = Field(..., description="UUID of participant")
    role: APRole = Field(..., description="AP debate role")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "first_speaker"
            }
        }


class APMatchConfig(BaseModel):
    """
    AP-specific match configuration.
    
    Attributes:
        tournament_id (Optional[str]): Tournament this match belongs to
        round_number (Optional[int]): Round number if in tournament
        adjudicator_id (Optional[str]): Judge/adjudicator UUID
    """
    tournament_id: Optional[str] = Field(None, description="Tournament ID if applicable")
    round_number: Optional[int] = Field(None, description="Round number", ge=1)
    adjudicator_id: Optional[str] = Field(None, description="Judge UUID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tournament_id": "tournament_123",
                "round_number": 1,
                "adjudicator_id": "judge_456"
            }
        }


class CreateMatchRequest(BaseModel):
    """
    Request to create a new AP match.
    
    Flow:
    1. Frontend/user initiates match creation
    2. Specifies motion, title, and all 6 participants
    3. Backend creates match in PENDING state
    4. Match moves to IN_PROGRESS when first speech is recorded
    
    Attributes:
        title (str): Match/debate title
        motion (str): The debate motion/resolution
        government (List[ParticipantInfo]): 3 government speakers
        opposition (List[ParticipantInfo]): 3 opposition speakers
        config (APMatchConfig): Optional tournament/judge details
    """
    title: str = Field(..., min_length=5, max_length=200, description="Match title")
    motion: str = Field(..., min_length=10, max_length=500, description="Debate motion/resolution")
    government: List[ParticipantInfo] = Field(..., min_items=3, max_items=3, description="3 government speakers")
    opposition: List[ParticipantInfo] = Field(..., min_items=3, max_items=3, description="3 opposition speakers")
    config: Optional[APMatchConfig] = Field(default=None, description="Optional config")
    
    @validator("government", "opposition")
    def validate_ap_roles(cls, speakers):
        """Ensure each side has exactly one speaker for each role."""
        roles = [speaker.role for speaker in speakers]
        required_roles = {APRole.FIRST_SPEAKER, APRole.SECOND_SPEAKER, APRole.WHIP}
        
        if set(roles) != required_roles:
            raise ValueError(f"Each side must have exactly one first_speaker, second_speaker, and whip")
        return speakers
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Resolving Technology Impact",
                "motion": "This house believes that AI development should be heavily regulated",
                "government": [
                    {"user_id": "user_1", "role": "first_speaker"},
                    {"user_id": "user_2", "role": "second_speaker"},
                    {"user_id": "user_3", "role": "whip"}
                ],
                "opposition": [
                    {"user_id": "user_4", "role": "first_speaker"},
                    {"user_id": "user_5", "role": "second_speaker"},
                    {"user_id": "user_6", "role": "whip"}
                ],
                "config": {
                    "tournament_id": "tournament_123",
                    "round_number": 1,
                    "adjudicator_id": "judge_1"
                }
            }
        }


class UpdateMatchStatusRequest(BaseModel):
    """
    Request to update match status.
    
    Allowed transitions:
    - pending → in_progress (when first speech recorded)
    - in_progress → completed (when judging submitted)
    - any → cancelled (at any time by creator or adjudicator)
    
    Attributes:
        status (MatchStatus): New status
        reason (Optional[str]): Reason for status change (required for cancellation)
    """
    status: MatchStatus = Field(..., description="New match status")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for change (required for cancel)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "reason": "Judging submitted"
            }
        }


# ============================================================================
# RESPONSE MODELS - What backend sends back
# ============================================================================

class SpeakerInfo(BaseModel):
    """
    Speaker/participant information in match response.
    
    Attributes:
        user_id (str): UUID
        role (APRole): Debate role
        name (str): Speaker display name
        spoke (bool): Has this speaker spoken yet?
        speech_duration (Optional[int]): Duration of their speech (if spoken)
        poi_made (Optional[int]): Points of information they made
        poi_received (Optional[int]): Points of information made against them
    """
    user_id: str
    role: APRole
    name: str
    spoke: bool = False
    speech_duration: Optional[int] = None
    poi_made: Optional[int] = None
    poi_received: Optional[int] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "user_1",
                "role": "first_speaker",
                "name": "John Doe",
                "spoke": True,
                "speech_duration": 285,
                "poi_made": 2,
                "poi_received": 1
            }
        }


class TeamInfo(BaseModel):
    """
    Team/side information in match response.
    
    Attributes:
        team_id (str): Unique team identifier
        side (DebateSide): Government or Opposition
        speakers (List[SpeakerInfo]): 3 speakers for this side
    """
    team_id: str
    side: DebateSide
    speakers: List[SpeakerInfo] = Field(min_items=3, max_items=3)
    
    class Config:
        from_attributes = True


class NextSpeaker(BaseModel):
    """
    Information about next speaker in debate sequence.
    
    Attributes:
        role (APRole): Their role
        side (DebateSide): Their team
        user_id (str): Their UUID
        order_position (int): Which speech (1-6)
    """
    role: APRole
    side: DebateSide
    user_id: str
    order_position: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "first_speaker",
                "side": "opposition",
                "user_id": "user_4",
                "order_position": 2
            }
        }


class MatchResponse(BaseModel):
    """
    Complete match information response.
    
    Used by: GET /api/v1/ap/matches/{id}
    
    Represents full match state including:
    - All participants and their details
    - Current debate status and progression
    - Next speaker information
    - Match metadata and timestamps
    """
    id: str = Field(..., description="Match UUID")
    title: str = Field(..., description="Match title")
    motion: str = Field(..., description="Debate motion")
    format: Literal["asian_parliamentary"] = "asian_parliamentary"
    status: MatchStatus = Field(..., description="Current match status")
    
    # Teams
    government: TeamInfo
    opposition: TeamInfo
    
    # Debate progression
    speeches_completed: int = Field(..., ge=0, le=6)
    current_speaker_index: Optional[int] = Field(None, ge=0, le=5, description="Index 0-5 of current speech")
    next_speaker: Optional[NextSpeaker] = None
    
    # AP-specific config
    adjudicator_id: Optional[str] = None
    tournament_id: Optional[str] = None
    round_number: Optional[int] = None
    
    # Timestamps
    created_at: datetime
    created_by: str = Field(..., description="UUID of user who created match")
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "match_uuid",
                "title": "Resolving Technology Impact",
                "motion": "This house believes that AI development should be heavily regulated",
                "format": "asian_parliamentary",
                "status": "in_progress",
                "government": {
                    "team_id": "team_1",
                    "side": "government",
                    "speakers": [
                        {
                            "user_id": "user_1",
                            "role": "first_speaker",
                            "name": "John Doe",
                            "spoke": True,
                            "speech_duration": 285,
                            "poi_made": 2,
                            "poi_received": 1
                        }
                    ]
                },
                "opposition": {
                    "team_id": "team_2",
                    "side": "opposition",
                    "speakers": []
                },
                "speeches_completed": 1,
                "current_speaker_index": 1,
                "next_speaker": {
                    "role": "first_speaker",
                    "side": "opposition",
                    "user_id": "user_4",
                    "order_position": 2
                },
                "adjudicator_id": "judge_1",
                "created_at": "2026-04-17T10:00:00Z",
                "created_by": "user_1",
                "started_at": "2026-04-17T10:05:00Z",
                "updated_at": "2026-04-17T10:10:00Z"
            }
        }


class MatchListItem(BaseModel):
    """
    Condensed match info for list view.
    
    Used by: GET /api/v1/ap/matches?skip=0&limit=10
    
    Lightweight version for listing multiple matches efficiently.
    """
    id: str
    title: str
    status: MatchStatus
    motion: str = Field(..., description="Truncate to 100 chars in response")
    speeches_completed: int
    government_side: str = "Government"
    opposition_side: str = "Opposition"
    created_at: datetime
    started_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    """
    Paginated list of matches response.
    
    Used by: GET /api/v1/ap/matches?skip=0&limit=10&status=in_progress
    
    Attributes:
        matches (List[MatchListItem]): List of match summaries
        total (int): Total count of matches (ignoring pagination)
        skip (int): Pagination offset
        limit (int): Pagination limit
    """
    matches: List[MatchListItem]
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "matches": [
                    {
                        "id": "match_1",
                        "title": "Technology and AI",
                        "status": "in_progress",
                        "motion": "This house believes...",
                        "speeches_completed": 3,
                        "government_side": "Government",
                        "opposition_side": "Opposition",
                        "created_at": "2026-04-17T10:00:00Z",
                        "started_at": "2026-04-17T10:05:00Z"
                    }
                ],
                "total": 15,
                "skip": 0,
                "limit": 10
            }
        }
