"""
British Parliamentary (BP) Case Prep Schemas.

Simple 2-schema pattern:
1. GenerateCasePrepRequest - Client sends motion + team + role
2. CasePrepResponse - Server returns resource info + role-specific prep
3. AIPrepResult - AI agent's structured output for case prep

Speaker Roles (BP Format — 8 speakers, 4 teams):
- Prime Minister (PM): Opening Government - Establishes case
- Leader of Opposition (LO): Opening Opposition - Challenges PM
- Deputy Prime Minister (DPM): Opening Government - Extends PM's case
- Deputy Leader of Opposition (DLO): Opening Opposition - Extends LO's case
- Member of Government (MG): Closing Government - Must introduce EXTENSION
- Member of Opposition (MO): Closing Opposition - Must introduce EXTENSION
- Government Whip (GW): Closing Government - Summarizes, weighs clashes
- Opposition Whip (OW): Closing Opposition - Summarizes, weighs clashes
"""

from typing import List
from enum import Enum
from pydantic import BaseModel, Field

from src.schemas.bp.matches import BPRole, BPTeam


# ENUMS (reused from matches.py via import)


# REQUEST
class GenerateCasePrepRequest(BaseModel):
    """Request to generate case prep for specific role in BP debate."""
    motion: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Debate motion/resolution to argue about"
    )
    team: BPTeam = Field(..., description="Your team (OG, OO, CG, CO)")
    role: BPRole = Field(..., description="Your speaker role in the debate")


# RESPONSE
class Argument(BaseModel):
    """Single debate argument with claim, reasoning, and impact."""
    claim: str = Field(description="Main claim/thesis")
    reasoning: str = Field(description="Logical reasoning/evidence")
    impact: str = Field(description="Why this matters/consequence if true")


class CasePrepResponse(BaseModel):
    """
    Case prep response - role-specific preparation for BP debate.
    
    Contains all information user needs to prepare for their specific role.
    """
    # Resource identifiers
    id: str = Field(description="Case prep record ID")
    user_id: str = Field(description="User who requested prep")
    match_id: str = Field(description="Match this prep is for")
    
    # Role context
    team: BPTeam = Field(description="Which team they're on")
    role: BPRole = Field(description="Their speaker role")
    
    # Role-specific preparation
    model_definition: str = Field(description="Case theory - framework for interpreting motion")
    arguments: List[Argument] = Field(description="Main arguments to make (3-5 per role)")
    counter_arguments: List[str] = Field(description="Anticipated opposing arguments")
    evidence: List[str] = Field(description="Supporting facts, statistics, examples")
    
    class Config:
        from_attributes = True


# AI AGENT OUTPUT
class AIPrepResult(BaseModel):
    """
    AI Agent Output Schema - Result from Prep Coach agent.
    
    This is the structured output from the prep_coach AI agent.
    Used by LangChain's with_structured_output() for response parsing.
    Returned to service layer for validation and persistence.
    """
    model_definition: str = Field(
        description="Case theory - framework for interpreting motion",
        min_length=20,
        max_length=2000
    )
    arguments: List[Argument] = Field(
        description="Main arguments to make (3-5 per role)",
        min_items=1,
        max_items=10
    )
    counter_arguments: List[str] = Field(
        description="Anticipated opposing arguments",
        default_factory=list,
        max_items=10
    )
    evidence: List[str] = Field(
        description="Supporting facts, statistics, examples",
        default_factory=list,
        max_items=20
    )
    
    class Config:
        from_attributes = True
