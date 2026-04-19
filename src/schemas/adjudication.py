"""
Adjudication Result Schemas: Structured output for the 5-phase pipeline.

Defines Pydantic models for:
- Macro-clashes
- WCM matrix entries
- Pillar scores
- Speaker grades
- Final adjudication result
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class MacroClash(BaseModel):
    """Represents a single macro-clash extracted from debate."""
    id: int
    theme: str
    description: str
    government_position: str
    opposition_position: str


class WCMEntry(BaseModel):
    """Single entry in Weighted Clash Matrix."""
    clash_id: int
    clash_theme: str
    weight: int = Field(..., ge=1, le=5, description="Importance (1-5)")
    weight_reasoning: str
    delta: int = Field(..., ge=-2, le=2, description="Winner (-2 to +2)")
    delta_reasoning: str
    weighted_score: int = Field(..., description="weight × delta")


class PillarScore(BaseModel):
    """Score for a single WUDC pillar."""
    definition: str
    government_score: float = Field(..., ge=0, le=25)
    opposition_score: float = Field(..., ge=0, le=25)
    reasoning: str


class PillarBreakdown(BaseModel):
    """Complete WUDC pillar breakdown for both teams."""
    matter: PillarScore
    manner: PillarScore
    method: PillarScore
    role: PillarScore
    pillar_reasoning: str
    
    @property
    def government_total(self) -> float:
        """Calculate total Government score (0-100)."""
        return (self.matter.government_score + 
                self.manner.government_score + 
                self.method.government_score + 
                self.role.government_score)
    
    @property
    def opposition_total(self) -> float:
        """Calculate total Opposition score (0-100)."""
        return (self.matter.opposition_score + 
                self.manner.opposition_score + 
                self.method.opposition_score + 
                self.role.opposition_score)
    
    @property
    def winning_team(self) -> str:
        """Determine winning team."""
        if self.government_total > self.opposition_total:
            return "Government"
        elif self.opposition_total > self.government_total:
            return "Opposition"
        else:
            return "Tie"


class SpeakerScore(BaseModel):
    """Individual speaker performance evaluation."""
    role: str
    side: str = Field(..., description="Government or Opposition")
    score: int = Field(..., ge=0, le=100)
    argument_quality: int = Field(..., ge=0, le=10)
    evidence_usage: int = Field(..., ge=0, le=10)
    responsiveness: int = Field(..., ge=0, le=10)
    structure: int = Field(..., ge=0, le=10)
    persona: int = Field(..., ge=0, le=10)
    feedback: str


class AdjudicationSummary(BaseModel):
    """Final adjudication summary."""
    adjudication: str
    key_decision_1: str
    key_decision_2: str
    key_decision_3: Optional[str] = None


class AdjudicationResult(BaseModel):
    """Complete adjudication result (all 5 phases)."""
    
    # Phase 1: Macro-clashes
    clashes: List[MacroClash]
    
    # Phase 2: WCM Matrix
    wcm_matrix: List[WCMEntry]
    net_logic_score: float
    
    # Phase 3: WUDC Pillars
    pillar_breakdown: PillarBreakdown
    
    # Phase 4: Speaker Scores
    speaker_scores: List[SpeakerScore]
    
    # Phase 5: Summary
    summary: AdjudicationSummary
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    
    @property
    def winning_team(self) -> str:
        """Get the winning team."""
        return self.pillar_breakdown.winning_team
    
    @property
    def government_score(self) -> float:
        """Get Government total score."""
        return self.pillar_breakdown.government_total
    
    @property
    def opposition_score(self) -> float:
        """Get Opposition total score."""
        return self.pillar_breakdown.opposition_total
    
    def to_database_dict(self) -> Dict:
        """
        Convert to format for database storage.
        
        Returns:
            Dict with clash_table and speaker_scores for Supabase JSONB fields
        """
        return {
            "winning_team": self.winning_team,
            "gov_total_score": self.government_score,
            "opp_total_score": self.opposition_score,
            "clash_table": {
                "clashes": [c.dict() for c in self.clashes],
                "wcm_matrix": [w.dict() for w in self.wcm_matrix],
                "net_logic_score": self.net_logic_score,
                "pillar_breakdown": self.pillar_breakdown.dict(),
                "summary": self.summary.dict()
            },
            "speaker_scores": [s.dict() for s in self.speaker_scores]
        }
