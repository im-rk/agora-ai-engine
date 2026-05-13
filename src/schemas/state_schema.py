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
    
    # === Timer: ABSOLUTE Timestamps (CRITICAL for rejoin!) ===
    # Unix timestamp when this turn expires
    # NEVER changes during the turn (even if user disconnects)
    # Extends only when user reconnects from PAUSED state
    turn_expires_at: Optional[int] = None
    
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
    # Cache of tokens generated so far (used for mid-stream rejoin)
    active_stream_buffer: str = ""
    
    # === Data ===
    transcript: List[dict] = []
    
    @property
    def time_remaining_seconds(self) -> int:
        """
        Calculate remaining time dynamically from absolute timestamp.
        
        This is the KEY to FAANG-level reconnection:
        - We store turn_expires_at (immutable, in Redis)
        - We CALCULATE time_remaining_seconds on every access
        - If user reconnects after 10 mins, this auto-corrects
        
        Example Timeline:
          T=0:00  turn_expires_at = 1715340300 (now + 300 secs)
          T=3:00  time_remaining = 1715340300 - now() = 180 seconds 
          T=3:00  User disconnects (WebSocket closes)
          T=8:00  User reconnects
                  turn_expires_at EXTENDS to 1715340600 (300 more seconds added)
                  time_remaining = 1715340600 - now() = 240 seconds (4 mins) 
        
        Returns:
            int: Seconds remaining (never negative, returns 0 if expired)
        """
        if not self.turn_expires_at:
            return 300  # Default 5 minutes if not initialized
        
        now = int(datetime.now(timezone.utc).timestamp())
        remaining = self.turn_expires_at - now
        return max(0, remaining)  # Never show negative time

