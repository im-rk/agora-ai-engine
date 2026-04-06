import os
import json
import redis.asyncio as redis
from typing import Optional
from src.schemas.state_schema import Turn,LiveMatchState
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

        if format_type.lower() == "asian parliamentary":
            schedule = [
                Turn(role="Prime Minister", side="Government", player_type="ai"),
                Turn(role="Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Deputy Prime Minister", side="Government", player_type="ai"),
                Turn(role="Deputy Leader of Opposition", side="Opposition", player_type="ai"),
                Turn(role="Government Whip", side="Government", player_type="ai"),
                Turn(role="Opposition Whip", side="Opposition", player_type="ai"),
            ]
        elif format_type.lower() == "british parliamentary":
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
        
        human_assigned=False

        if preferred_role:
            for turn in schedule:
                if turn.role.lower()==preferred_role.lower():
                    turn.player_type="human"
                    human_assigned=True
                    break

        if not human_assigned:
            for turn in schedule:
                if turn.side.lower()==human_side.lower():
                    turn.player_type="human"
                    break
        
        return schedule
    
    async def initialize_match(self, match_id: str, human_side: str, format_type: str, preferred_role: str = None) -> LiveMatchState:
        """Creates a initial game state and save it to Redis."""
        await self._ensure_connection()
        full_schedule = self._generate_schedule(format_type, human_side, preferred_role)
        state = LiveMatchState(
            match_id=match_id,
            status="in_progress",
            current_turn_index=0,
            schedule=full_schedule
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
    
state_manager=MatchStateManager()
