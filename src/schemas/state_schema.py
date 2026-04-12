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
    to ask a brief question. The current speaker can accept or decline.

    Stored in state so the Adjudicator can score POI interaction
    and the History API can replay what happened during the debate.
    """
    offered_by: str                      # "human" or "ai" — who offered the POI
    poi_text: str                        # The actual question/challenge text
    outcome: str                         # "accepted" or "declined"
    response_text: Optional[str] = None  # The spoken response if accepted, or decline phrase
    offered_at_second: int = 0           # How many seconds into the speech it was offered


class LiveMatchState(BaseModel):
    """
    The complete in-memory state of a live debate match.

    Storage key in Redis: "match_state:{match_id}"

    Ownership model (aligned with friend's Go PR #5):
      - Python writes the full state (schedule, transcript, POIs, status)
      - Go patches ONLY current_turn_index using map[string]interface{}
        (all other fields survive Go's patch because unknown JSON keys are preserved)
      - Both services use the SAME key: "match_state:{match_id}"
      - Go publishes TURN_CHANGED as a notification only — no data in payload
      - Python reads fresh state from Redis when it receives TURN_CHANGED
    """
    match_id: str
    status: str = "waiting"            # "waiting" | "in_progress" | "finished"
    current_turn_index: int = 0        # Go increments this. Python reads it from Redis.
    schedule: List[Turn]               # Full ordered list of speakers (set on match init)
    time_remaining_seconds: int = 300
    transcript: List[Dict[str, Any]] = []  # All speeches delivered so far

    # POI tracking fields — all have defaults so existing Redis state still deserializes
    poi_window_open: bool = False              # Is it valid to offer a POI right now?
    pois_this_turn: List[POIRecord] = []       # POIs from the current turn (for per-turn limits)
    all_pois: List[POIRecord] = []             # All POIs from the full match (for Adjudicator)
    total_pois_accepted_by_ai: int = 0        # Running count: AI accepted N human POIs
    total_pois_accepted_by_human: int = 0     # Running count: Human accepted N AI POIs
