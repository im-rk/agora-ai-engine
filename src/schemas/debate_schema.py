from pydantic import BaseModel, Field
from typing import Optional,List

class MatchStartRequest(BaseModel): 
    motion_text: str = Field(..., description="The topic of the debate")
    side: str = Field(..., description="Government or opposition")
    format: str = Field(default="Asian Parliamentary", description="The debate format") # <-- Fixed spelling
    user_id: str

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