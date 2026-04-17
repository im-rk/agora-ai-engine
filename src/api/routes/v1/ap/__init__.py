"""
Asian Parliamentary (AP) API Routes.

API endpoint definitions for AP debate format.

Features:
- matches.py: Match creation, listing, management
- debates.py: Speech recording, debate state (future)
- case_prep.py: Case prep coaching (future)
- judging.py: Judging submission (future)
- statistics.py: User statistics (future)

Router Registration:
All routers are imported and registered in v1/__init__.py
"""

from fastapi import APIRouter
from .matches import router as matches_router

# Create AP router - prefix will be added by parent router
ap_router = APIRouter()

# Include all AP sub-routes
ap_router.include_router(matches_router, prefix="/matches", tags=["AP Matches"])

__all__ = ["ap_router"]
