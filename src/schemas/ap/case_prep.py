"""
Asian Parliamentary (AP) Case Prep Schemas.

Simple 2-schema pattern:
1. GenerateCasePrepRequest - Client sends motion + side + role
2. CasePrepResponse - Server returns resource info + role-specific prep

Speaker Roles (AP Format):
- Prime Minister (PM): Characterises and establishes ideas, stakeholders, narratives
- Leader of Opposition (LO): Lays characterisation for opposition, challenges PM
- Deputy Prime Minister (DPM): Argues points in government's favour
- Deputy Leader of Opposition (DLO): Argues points in opposition's favour
- Government Whip: Rebuts opposition, weighs clashes, identifies wins
- Opposition Whip: Rebuts government, weighs clashes, identifies wins
"""

from typing import List
from enum import Enum
from pydantic import BaseModel, Field


# ENUMS
class APRole(str, Enum):
    """AP debate speaker roles."""
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


# REQUEST
class GenerateCasePrepRequest(BaseModel):
    """Request to generate case prep for specific role in debate."""
    motion: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Debate motion/resolution to argue about"
    )
    side: DebateSide = Field(..., description="Government or Opposition")
    role: APRole = Field(..., description="Your speaker role in the debate")


# RESPONSE
class Argument(BaseModel):
    """Single debate argument with claim, reasoning, and impact."""
    claim: str = Field(description="Main claim/thesis")
    reasoning: str = Field(description="Logical reasoning/evidence")
    impact: str = Field(description="Why this matters/consequence if true")


class CasePrepResponse(BaseModel):
    """
    Case prep response - role-specific preparation for debate.
    
    Contains all information user needs to prepare for their specific role.
    """
    # Resource identifiers
    id: str = Field(description="Case prep record ID")
    user_id: str = Field(description="User who requested prep")
    match_id: str = Field(description="Match this prep is for")
    
    # Role context
    side: DebateSide = Field(description="Which side they're on")
    role: APRole = Field(description="Their speaker role")
    
    # Role-specific preparation
    model_definition: str = Field(description="Case theory - framework for interpreting motion")
    arguments: List[Argument] = Field(description="Main arguments to make (3-5 per role)")
    counter_arguments: List[str] = Field(description="Anticipated opposing arguments")
    evidence: List[str] = Field(description="Supporting facts, statistics, examples")
    
    class Config:
        from_attributes = True
