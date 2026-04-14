from pydantic import BaseModel, Field
from typing import Optional,List

class MatchStartRequest(BaseModel): 
    motion_text: str = Field(...)
    side: str = Field(...)
    format: str = Field(default="ap") 
    skill_level: str = Field(default="intermediate")
    preferred_role: Optional[str] = Field(default=None)


class MatchStartResponse(BaseModel):
    session_id: str
    case_prep_id: str
    message: str

class CasePrepResponse(BaseModel):
    id: str
    side: str
    arguments: Optional[List[dict]] = []
    counter_arguments: Optional[List[dict]] = []
    evidence: Optional[List[dict]] = []