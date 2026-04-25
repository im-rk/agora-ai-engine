"""
British Parliamentary (BP) format-specific prompts and role constraints.

This module exports BP-specific implementations for the 4-phase FAANG pipeline.
- Phase 1: Parse clash matrix using BP_CLASH_MATRIX_PARSER_PROMPT
- Phase 2: Generate queries using BP_QUERY_SYNTHESIS_PROMPT with BP role constraints
- Phase 3: Retrieve evidence (same RAG as other formats, but side-aware)
- Phase 4: Generate response using BP_RESPONSE_GENERATION_PROMPT with role instructions

BP Format - 8 Speakers (4 Teams):
Opening Government (OG):
  1. Prime Minister (PM)
  3. Deputy Prime Minister (DPM)

Opening Opposition (OO):
  2. Leader of Opposition (LO)
  4. Deputy Leader of Opposition (DLO)

Closing Government (CG):
  5. Member of Government (MG)
  7. Government Whip (GW) - Rebuttal only

Closing Opposition (CO):
  6. Member of Opposition (MO)
  8. Opposition Whip (OW) - Rebuttal only

Key Differences from AP:
- Opening benches provide initial cases
- Closing benches rebuild/undo opposing cases and rank teams
- 4 teams ranked 1st-4th (24 possible outcomes)
- 7-minute speeches
- No new content in whip speeches

Usage:
    from src.ai.prompts.bp import (
        BP_ROLE_CONSTRAINTS,
        get_bp_role_instructions,
        normalize_bp_role,
        BP_CLASH_MATRIX_PARSER_PROMPT,
        BP_QUERY_SYNTHESIS_PROMPT,
        BP_RESPONSE_GENERATION_PROMPT,
    )
"""

from src.ai.prompts.bp.debater_prompts import (
    BP_ROLE_CONSTRAINTS,
    get_bp_role_instructions,
    normalize_bp_role,
    BP_CLASH_MATRIX_PARSER_PROMPT,
    BP_QUERY_SYNTHESIS_PROMPT,
    BP_RESPONSE_GENERATION_PROMPT,
)

__all__ = [
    'BP_ROLE_CONSTRAINTS',
    'get_bp_role_instructions',
    'normalize_bp_role',
    'BP_CLASH_MATRIX_PARSER_PROMPT',
    'BP_QUERY_SYNTHESIS_PROMPT',
    'BP_RESPONSE_GENERATION_PROMPT',
]
