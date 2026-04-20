"""
Asian Parliamentary (AP) Debate Prompts and Constraints.

Exports:
- AP_ROLE_CONSTRAINTS: Dictionary of AP role-specific constraints
- get_ap_role_instructions: Function to get role-specific instructions
- AP_CLASH_MATRIX_PARSER_PROMPT: Phase 1 prompt
- AP_QUERY_SYNTHESIS_PROMPT: Phase 2 prompt  
- AP_RESPONSE_GENERATION_PROMPT: Phase 4 prompt
"""

from .debater_prompts import (
    AP_ROLE_CONSTRAINTS,
    get_ap_role_instructions,
    AP_CLASH_MATRIX_PARSER_PROMPT,
    AP_QUERY_SYNTHESIS_PROMPT,
    AP_RESPONSE_GENERATION_PROMPT,
)

__all__ = [
    'AP_ROLE_CONSTRAINTS',
    'get_ap_role_instructions',
    'AP_CLASH_MATRIX_PARSER_PROMPT',
    'AP_QUERY_SYNTHESIS_PROMPT',
    'AP_RESPONSE_GENERATION_PROMPT',
]
