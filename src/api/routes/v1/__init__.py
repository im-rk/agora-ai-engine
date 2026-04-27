"""
API v1 routes.

Routes organized by feature:
- Authentication: /api/v1/auth/...
- Asian Parliamentary: /api/v1/ap/...
- British Parliamentary: /api/v1/bp/... (future)
- Case Preparation: /api/v1/case-prep/... (future)

Each route module is registered here with appropriate prefix and tags.
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .ap import ap_router
from .bp import bp_router
from .users import router as users_router

# ============================================================================
# Create v1 router with all feature routes
# ============================================================================

v1_router = APIRouter(prefix="/api/v1")

# Authentication endpoints
v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Asian Parliamentary endpoints
v1_router.include_router(ap_router, prefix="/ap", tags=["Asian Parliamentary"])

# British Parliamentary endpoints
v1_router.include_router(bp_router, prefix="/bp", tags=["British Parliamentary"])

# User aggregate stats
v1_router.include_router(users_router, prefix="/users", tags=["Users"])

# Case Preparation endpoints - future
# v1_router.include_router(case_prep_router, prefix="/case-prep", tags=["Case Prep"])

__all__ = ["v1_router"]
