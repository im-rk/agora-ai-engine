from typing import Optional
from src.schemas.state_schema import LiveMatchState
from src.schemas.event_schema import BaseEvent


class RuleDecision:
    def __init__(
        self,
        should_ai_speak: bool = False,
        should_advance_turn: bool = False,
        is_match_finished: bool = False
    ):
        self.should_ai_speak = should_ai_speak
        self.should_advance_turn = should_advance_turn
        self.is_match_finished = is_match_finished




def evaluate_rules(event: BaseEvent, state: LiveMatchState) -> RuleDecision:
    decision = RuleDecision()

    if event.type == "START_MATCH":
        current_turn = state.schedule[state.current_turn_index]

        if current_turn.player_type == "ai":
            decision.should_ai_speak = True

        return decision
    
    if event.type == "TURN_CHANGED":
        next_turn = state.schedule[state.current_turn_index]

        if next_turn.player_type == "ai":
            decision.should_ai_speak = True

        return decision

    if event.type == "USER_SPOKE":
        decision.should_advance_turn = True
        return decision