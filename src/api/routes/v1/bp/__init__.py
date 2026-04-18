"""
British Parliamentary (BP) API Routes.

API endpoint definitions for BP debate format.

Features:
- matches.py: Match creation, listing, management
- case_prep.py: Case prep generation and retrieval (nested under matches)
- debates.py: Speech recording, debate state (future)
- judging.py: Judging submission (future)
- statistics.py: User statistics (future)

Router Registration:
All routers are imported and registered here
Then included in v1/__init__.py with /bp prefix
"""

from fastapi import APIRouter
from .matches import router as matches_router
from .case_prep import router as case_prep_router

# ============================================================================
# Create BP router - prefix will be added by parent router
# ============================================================================

bp_router = APIRouter()

# Match endpoints
bp_router.include_router(matches_router, prefix="/matches", tags=["BP Matches"])

# Nested: Match → Case Prep endpoints
bp_router.include_router(
    case_prep_router,
    prefix="/matches/{match_id}/case-prep",
    tags=["BP Case Prep"]
)

__all__ = ["bp_router"]
