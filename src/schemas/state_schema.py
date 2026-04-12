from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Turn(BaseModel):
    """Represents one speaker slot in the debate schedule."""
    role: str          # e.g. "Prime Minister", "Leader of Opposition"
    side: str          # "Government" or "Opposition"
    player_type: str   # "human" or "ai"


class POIRecord(BaseModel):
    """
    Records a single Point of Information event during a turn.
    
    A POI is when a debater (who is not currently speaking) interrupts
    to ask a brief question. The speaker can accept or decline.
    
    This is stored in state so the Adjudicator can score POI interaction
    and so the History API can show what happened during the debate.
    """
    offered_by: str                    # "human" or "ai" — who offered the POI
    poi_text: str                      # The actual question/challenge text
    outcome: str                       # "accepted" or "declined"
    response_text: Optional[str] = None  # AI's response if accepted (or decline phrase)
    offered_at_second: int = 0         # How many seconds into the speech it was offered


class LiveMatchState(BaseModel):
    """
    The complete in-memory state of a live debate match.
    Stored in Redis under key: "match_state:{match_id}"
    Only Python reads/writes this. Go has its own minimal state at "go_state:{match_id}".
    """
    match_id: str
    status: str = "waiting"        # "waiting" | "in_progress" | "finished"
    current_turn_index: int = 0    # Synced from Go's TURN_CHANGED event
    schedule: List[Turn]           # The full ordered list of speakers
    time_remaining_seconds: int = 300
    transcript: List[Dict[str, Any]] = []  # All speeches so far

    # --- POI tracking fields (added for Step 3 — all have defaults so old states still load) ---
    poi_window_open: bool = False              # Is it currently valid to offer a POI?
    pois_this_turn: List[POIRecord] = []       # POIs during the CURRENT turn (reset each turn)
    all_pois: List[POIRecord] = []             # All POIs from the entire match (for adjudicator)
    total_pois_accepted_by_ai: int = 0        # Running count: AI accepted N POIs from human
    total_pois_accepted_by_human: int = 0     # Running count: Human accepted N POIs from AI
