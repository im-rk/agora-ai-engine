"""
API dependencies.

Shared dependencies for all routes:
- get_current_user: JWT validation for protected routes
"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional
from sqlalchemy.orm import Session
import logging

from src.core.database import get_db
from src.core.security import verify_token
from src.schemas.auth import CurrentUserData

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUserData:
    """
    Get current authenticated user from JWT token in Authorization header.

    Validates JWT token and extracts user data for use in protected routes.
    Expected header format: Authorization: Bearer {jwt_token}

    Args:
        authorization (Optional[str]): Authorization header value.
        db (Session): Database session dependency.

    Returns:
        CurrentUserData: Contains user_id and email extracted from JWT.

    Raises:
        HTTPException(401): If Authorization header is missing.
        HTTPException(401): If header format is invalid (not "Bearer {token}").
        HTTPException(401): If JWT token is invalid or expired.
        RequestValidationError: If header parsing fails.
    """
    if not authorization:
        logger.warning("Missing authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token from "Bearer {token}"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError()
    except (ValueError, IndexError):
        logger.warning("Invalid authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer {token}"
        )
    
    # Verify token and extract claims
    token_data = verify_token(token)
    
    if not token_data:
        logger.warning("Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    logger.info(f"User authenticated: {token_data.email}")
    
    return CurrentUserData(
        user_id=token_data.user_id,
        email=token_data.email
    )
