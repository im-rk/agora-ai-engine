"""
Debate Rules Engine

Single source of truth for all format-specific debate rules.
Import this wherever you need timing or POI limits — never hardcode numbers.

Why a dataclass and not a dict?
  A dict gives you rules["poi_window_start"] — typo-prone, no autocomplete.
  A dataclass gives you rules.poi_window_start — type-safe, IDE-complete.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class FormatRules:
    """All timing and limit rules for one debate format."""
    speech_duration_seconds: int          # Total length of each speech
    poi_window_start: int                  # When POI window opens (seconds into speech)
    poi_window_end: int                    # When POI window closes (seconds into speech)
    max_pois_to_offer_per_speech: int     # Max POIs one side can OFFER during one speech
    max_pois_to_accept_per_speech: int    # Max POIs a speaker should ACCEPT in one speech


# All supported format configurations.
# Keys are lowercase — always use format_type.lower() when looking up.
FORMAT_RULES: Dict[str, FormatRules] = {
    "ap": FormatRules(
        speech_duration_seconds=300,      # 5 minutes
        poi_window_start=60,              # Opens at 1:00
        poi_window_end=240,               # Closes at 4:00
        max_pois_to_offer_per_speech=4,
        max_pois_to_accept_per_speech=2
    ),
    "asian parliamentary": FormatRules(
        speech_duration_seconds=300,
        poi_window_start=60,
        poi_window_end=240,
        max_pois_to_offer_per_speech=4,
        max_pois_to_accept_per_speech=2
    ),
    "bp": FormatRules(
        speech_duration_seconds=420,      # 7 minutes
        poi_window_start=60,
        poi_window_end=360,               # Closes at 6:00
        max_pois_to_offer_per_speech=4,
        max_pois_to_accept_per_speech=2
    ),
    "british parliamentary": FormatRules(
        speech_duration_seconds=420,
        poi_window_start=60,
        poi_window_end=360,
        max_pois_to_offer_per_speech=4,
        max_pois_to_accept_per_speech=2
    ),
}

# Default fallback
_DEFAULT_RULES = FORMAT_RULES["ap"]


def get_rules(format_type: str) -> FormatRules:
    """Get the rules for a debate format. Falls back to AP if unknown."""
    return FORMAT_RULES.get(format_type.lower(), _DEFAULT_RULES)


def is_poi_window_open(format_type: str, elapsed_seconds: int) -> bool:
    """
    Returns True if POIs can currently be offered.
    
    Use before calling SniperAgent — if window is closed, don't even call the LLM.
    
    Args:
        format_type: "ap", "bp", etc.
        elapsed_seconds: How many seconds into the current speech
    """
    rules = get_rules(format_type)
    return rules.poi_window_start <= elapsed_seconds <= rules.poi_window_end
