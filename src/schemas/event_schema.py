from pydantic import BaseModel
from typing import Optional, Dict, Any


class BaseEvent(BaseModel):
    type: str
    match_id: str
    payload: Optional[Dict[str, Any]] = None

class EventType:
    START_MATCH = "START_MATCH"
    TURN_CHANGED = "TURN_CHANGED"
    USER_SPOKE = "USER_SPOKE"
    AI_TOKEN = "AI_TOKEN"
    AI_THOUGHT_START = "AI_THOUGHT_START"
    AI_THOUGHT_COMPLETE = "AI_THOUGHT_COMPLETE"
    MATCH_ENDED = "MATCH_ENDED"