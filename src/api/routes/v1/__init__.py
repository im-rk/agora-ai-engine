"""
API v1 routes.

Currently only auth is implemented.
Authentication: /api/auth/...
"""

from fastapi import APIRouter
from .auth import router as auth_router

# Create v1 router with auth endpoints
v1_router = APIRouter(prefix="/api")
v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

__all__ = ["v1_router"]
