import os
import json
import redis.asyncio as redis
from typing import Optional
from datetime import datetime, timezone
from src.schemas.state_schema import Turn, LiveMatchState
from src.core.config import settings

class MatchStateManager:
    def __init__(self):
        redis_url = settings.REDIS_URL
        self.redis_url = redis_url
        self.redis = None  # Lazy initialization
    
    async def _ensure_connection(self):
        """Lazily initialize Redis connection on first use."""
        if self.redis is None:
            if not self.redis_url:
                raise ValueError("redis url not found")
            self.redis = redis.from_url(self.redis_url, decode_responses=True)

    def _generate_schedule(self,format_type:str,human_side:str,preferred_role:Optional[str]=None)->list[Turn]:
        """Builds the exact turn order based on the debate format"""

        if format_type.lower() in  ["asian parliamentary", "ap"]:
            schedule = [
                Turn(role="Prime Minister", side="Government", player_type="ai"),
                Turn(role="Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Deputy Prime Minister", side="Government", player_type="ai"),
                Turn(role="Deputy Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Government Whip", side="Government", player_type="ai"),
                Turn(role="Opposition Whip", side="Opposition", player_type="ai"),
            ]
        elif format_type.lower() in ["british parliamentary", "bp"]:
            schedule = [
                Turn(role="Prime Minister", side="Government", player_type="ai"),
                Turn(role="Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Deputy Prime Minister", side="Government", player_type="ai"),
                Turn(role="Deputy Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Member of Government", side="Government", player_type="ai"),
                Turn(role="Member of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Government Whip", side="Government", player_type="ai"),
                Turn(role="Opposition Whip", side="Opposition", player_type="ai"),
            ]
        else:
            # Fallback for simple 1v1
            schedule = [
                Turn(role="Prime Minister", side="Government", player_type="ai"),
                Turn(role="Leader of Opposition", side="Opposition", player_type="ai")
            ]
        
        human_assigned = False

        if preferred_role:
            normalized_pref = preferred_role.lower().replace("_", " ")
            for turn in schedule:
                if turn.role.lower() == normalized_pref:
                    turn.player_type = "human"
                    human_assigned = True
                    break

        if not human_assigned:
            # Normalize BP teams (e.g. 'opening_government' -> 'government')
            normalized_side = human_side.lower()
            if "government" in normalized_side:
                normalized_side = "government"
            elif "opposition" in normalized_side:
                normalized_side = "opposition"
                
            for turn in schedule:
                if turn.side.lower() == normalized_side:
                    turn.player_type = "human"
                    break
        
        return schedule
    
    def _get_turn_duration(self, format_type: str, role: str) -> int:
        """
        Get the time allocated for a specific speaker based on format and role.
        
        AP (Asian Parliamentary):
        - All speakers: 5 minutes (300 seconds)
        
        BP (British Parliamentary):
        - Prime Minister, Leader of Opposition: 7 minutes (420 seconds)
        - Deputy PM, Deputy LO: 7 minutes (420 seconds)
        - Members: 4 minutes (240 seconds)
        - Whips: 4 minutes (240 seconds)
        
        Returns:
            int: Turn duration in seconds
        """
        format_lower = format_type.lower()
        role_lower = role.lower()
        
        if format_lower in ["asian parliamentary", "ap"]:
            # AP: All speakers get 5 minutes
            return 300  # 5 minutes
        
        elif format_lower in ["british parliamentary", "bp"]:
            # BP: Variable times based on role
            if "prime minister" in role_lower or "leader of opposition" in role_lower:
                return 420  # 7 minutes for opening speakers
            elif "deputy" in role_lower:
                return 420  # 7 minutes for deputy roles
            elif "member" in role_lower or "whip" in role_lower:
                return 240  # 4 minutes for members and whips
            else:
                return 300  # Default to 5 minutes
        
        else:
            return 300  # Default to 5 minutes for unknown formats
    
    def _calculate_match_duration(self, format_type: str) -> int:
        """
        Calculate total match duration in seconds based on debate format.
        
        AP (Asian Parliamentary): 6 speakers × 5 minutes = 1800 seconds
        BP (British Parliamentary): 8 speakers (varied times) ≈ 3600 seconds
        
        Returns:
            int: Total match duration in seconds
        """
        if format_type.lower() in ["asian parliamentary", "ap"]:
            return 6 * 300  # 6 speakers × 5 mins = 1800 seconds
        elif format_type.lower() in ["british parliamentary", "bp"]:
            # BP: 2× PM/LO (7 min each) + 2× Deputy (7 min each) + 2× Member (4 min each) + 2× Whip (4 min each)
            return (2 * 420) + (2 * 420) + (2 * 240) + (2 * 240)  # 1680 + 1680 + 480 + 480 = 3840 seconds
        else:
            return 10 * 300  # Default 50 mins for unknown format
    
    async def initialize_match(self, match_id: str, human_side: str, format_type: str, preferred_role: str = None) -> LiveMatchState:
        """Creates a initial game state and save it to Redis."""
        await self._ensure_connection()
        full_schedule = self._generate_schedule(format_type, human_side, preferred_role)
        
        # Set match start time (absolute timestamp, never changes)
        now = int(datetime.now(timezone.utc).timestamp())
        
        # Get the turn duration for the first speaker
        first_speaker_role = full_schedule[0].role if full_schedule else "Prime Minister"
        first_turn_duration = self._get_turn_duration(format_type, first_speaker_role)
        
        state = LiveMatchState(
            match_id=match_id,
            format_type=format_type,
            status="IN_PROGRESS",  # Uppercase to match Literal enum
            current_turn_index=0,
            schedule=full_schedule,
            # === NEW TIMER MODEL ===
            match_started_at=now,                                      # When match began
            match_duration_seconds=self._calculate_match_duration(format_type),  # Total duration
            current_turn_duration_seconds=first_turn_duration,         # Current speaker's turn (varies by role/format)
            total_offline_duration=0,                                  # No offline time yet
            # === CONNECTION & AI STATE ===
            is_user_connected=True,  # User starts connected
            last_connected_at=now,  # Track when connection established
            ai_stream_status="IDLE",  # No AI generating yet
            active_stream_buffer="",  # No buffer yet
        )

        await self.update_state(state)
        return state
    
    async def get_state(self, match_id: str) -> Optional[LiveMatchState]:
        """Fetches the state from the Redis and parses it back into pydantic."""
        await self._ensure_connection()
        state_json = await self.redis.get(f"match_state:{match_id}")
        if not state_json:
            return None
        
        return LiveMatchState.model_validate_json(state_json)
    
    async def update_state(self, state: LiveMatchState):
        """Saves an updated pydantic state back to Redis."""
        await self._ensure_connection()
        state_json = state.model_dump_json()
        await self.redis.set(f"match_state:{state.match_id}", state_json, ex=7200)
    
    async def update_turn_duration(self, match_id: str, format_type: str, speaker_role: str):
        """
        Update the current turn duration based on speaker role and format.
        Call this when the turn changes to update current_turn_duration_seconds.
        """
        state = await self.get_state(match_id)
        if state:
            new_duration = self._get_turn_duration(format_type, speaker_role)
            state.current_turn_duration_seconds = new_duration
            await self.update_state(state)
            return new_duration
        return None

state_manager=MatchStateManager()
