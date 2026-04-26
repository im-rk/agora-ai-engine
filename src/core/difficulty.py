from pydantic import BaseModel


class DebateDifficultyConfig(BaseModel):
    level_name: str

    # Lever 1: Information
    max_search_queries: int
    rag_top_k: int

    # Lever 2: Strategy / Memory
    argument_drop_probability: float

    # Lever 3: LLM Parameters
    temperature: float
    persona_modifier: str


DIFFICULTY_MATRIX = {
    "beginner": DebateDifficultyConfig(
        level_name="beginner",
        max_search_queries=1,
        rag_top_k=1,
        argument_drop_probability=0.5,
        temperature=0.8,
        persona_modifier=(
            "You are a novice debater. Your logic is sometimes flawed. "
            "Use simple vocabulary. Do not use debate jargon."
        ),
    ),
    "intermediate": DebateDifficultyConfig(
        level_name="intermediate",
        max_search_queries=2,
        rag_top_k=3,
        argument_drop_probability=0.1,
        temperature=0.4,
        persona_modifier=(
            "You are an average competitive debater. You are logical but "
            "occasionally miss deep systemic impacts."
        ),
    ),
    "advanced": DebateDifficultyConfig(
        level_name="advanced",
        max_search_queries=4,
        rag_top_k=5,
        argument_drop_probability=0.0,
        temperature=0.1,
        persona_modifier=(
            "You are a World Universities Debating Champion. Speak with ruthless "
            "precision. Weigh all impacts mathematically. Use high-level rhetorical structure."
        ),
    ),
}


def get_difficulty_config(level: str) -> DebateDifficultyConfig:
    """Return difficulty config; defaults to intermediate for unknown levels."""
    if not level:
        return DIFFICULTY_MATRIX["intermediate"]

    normalized = level.strip().lower()

    # Accept existing app labels as aliases.
    aliases = {
        "easy": "beginner",
        "medium": "intermediate",
        "hard": "advanced",
    }
    normalized = aliases.get(normalized, normalized)

    return DIFFICULTY_MATRIX.get(normalized, DIFFICULTY_MATRIX["intermediate"])