from pydantic import BaseModel
from typing import Dict


class AdjudicationResultSchema(BaseModel):
    winning_team: str
    gov_total_score: float
    opp_total_score: float
    speaker_scores: Dict[str, float]
    feedback: str