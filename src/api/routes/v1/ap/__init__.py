"""
Asian Parliamentary (AP) API Routes.

API endpoint definitions for AP debate format.

Features:
- matches.py: Match creation, listing, management
- case_prep.py: Case prep generation and retrieval (nested under matches)
- debates.py: Speech recording, debate state (future)
- judging.py: Judging submission (future)
- statistics.py: User statistics (future)

Router Registration:
All routers are imported and registered here
Then included in v1/__init__.py with /ap prefix
"""

from fastapi import APIRouter
from .matches import router as matches_router
from .case_prep import router as case_prep_router

# Import the new adjudications router
try:
    from src.api.rest.adjudications import router as adjudications_router
    HAS_ADJUDICATIONS = True
except ImportError:
    HAS_ADJUDICATIONS = False

# ============================================================================
# Create AP router - prefix will be added by parent router
# ============================================================================

ap_router = APIRouter()

# Match endpoints
ap_router.include_router(matches_router, prefix="/matches", tags=["AP Matches"])

# Nested: Match → Case Prep endpoints
ap_router.include_router(
    case_prep_router,
    prefix="/matches/{match_id}/case-prep",
    tags=["AP Case Prep"]
)

# Adjudication endpoints (if available)
if HAS_ADJUDICATIONS:
    ap_router.include_router(
        adjudications_router,
        tags=["AP Adjudication"]
    )

__all__ = ["ap_router"]
