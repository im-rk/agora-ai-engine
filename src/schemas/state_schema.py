from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime, timezone

class Turn(BaseModel):
    role: str
    side: str
    player_type: str

class LiveMatchState(BaseModel):
    # === Core ===
    match_id: str
    format_type: str = "AP"
    
    # === Status (Enhanced with PAUSED for disconnect recovery) ===
    status: Literal["WAITING", "IN_PROGRESS", "PAUSED", "COMPLETED", "ABANDONED"] = "WAITING"
    
    # === Turn Management ===
    current_turn_index: int = 0
    schedule: List[Turn]
    
    # === Timer: Match-based with offline tracking (CRITICAL for rejoin!) ===
    # Unix timestamp when match started (set once, never changes)
    match_started_at: int = 0
    # Total duration of entire match in seconds (computed from format)
    # AP = 1800 (6 speakers × 5 mins), BP = 2400 (8 speakers × 5 mins)
    match_duration_seconds: int = 1800
    # Duration of current speaker's turn in seconds (300 for AP, varies for BP)
    current_turn_duration_seconds: int = 300
    # Accumulates all disconnection periods (grows when user rejoins)
    total_offline_duration: int = 0
    
    # === Connection State (NEW - for rejoin tracking) ===
    # Whether user is currently connected on WebSocket
    is_user_connected: bool = True
    # Unix timestamp of last successful connection
    last_connected_at: Optional[int] = None
    
    # === AI Generation State (NEW - for mid-stream rejoin recovery) ===
    # Track if AI is generating, paused, or done
    # "IDLE" = not started, "STREAMING" = generating tokens, 
    # "PAUSED" = interrupted (user disconnected), "COMPLETED" = finished
    ai_stream_status: Literal["IDLE", "STREAMING", "PAUSED", "COMPLETED"] = "IDLE"
    # Cache of tokens generated so far (used for rejoin recovery)
    active_stream_buffer: str = ""
    # Unix timestamp of when last audio chunk was sent to user
    # Gateway uses this to know which chunks to resend on rejoin
    chunks_last_sent_at: Optional[int] = None
    
    # === Data ===
    transcript: List[dict] = []
    
    @property
    def time_remaining_seconds(self) -> int:
        """
        Calculate remaining time based on active time (excluding offline periods).
        
        Timer Logic:
        - match_started_at: When match began (absolute, never changes)
        - current_turn_duration_seconds: How long THIS speaker gets (e.g., 300 for AP)
        - total_offline_duration: Time accumulated from all disconnections
        
        Calculation:
        1. elapsed_time = now() - match_started_at
        2. active_time = elapsed_time - total_offline_duration (subtract offline periods)
        3. time_remaining = current_turn_duration_seconds - active_time
        
        Example Timeline (AP Speaker, 5 min turn):
          T=0:00  match_started_at = Unix(0), elapsed = 0, active = 0, remaining = 300
          T=2:00  elapsed = 120, active = 120, remaining = 180
          T=3:00  User disconnects (offline_duration = +180 on rejoin)
          T=8:00  User rejoins:
                  elapsed = 480
                  active = 480 - 180 = 300
                  remaining = 300 - 300 = 0 (turn is over!)
        
        Returns:
            int: Seconds remaining in current speaker's turn (never negative)
        """
        now = int(datetime.now(timezone.utc).timestamp())
        elapsed_time = now - self.match_started_at
        active_time = elapsed_time - self.total_offline_duration
        remaining = self.current_turn_duration_seconds - active_time
        return max(0, remaining)  # Never show negative time

