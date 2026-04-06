from pydantic import BaseModel
from typing import List,Optional

class Turn(BaseModel):
    role:str
    side: str
    player_type: str

class LiveMatchState(BaseModel):
    match_id: str
    status : str="waiting"
    current_turn_index: int =0
    schedule : List[Turn]
    time_remaining_seconds : int =300
    transcript: List[dict]=[]

