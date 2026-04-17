"""
Authentication routes.

Only endpoint: POST /api/auth/verify-supabase
- Frontend handles signup/login with Supabase
- Frontend sends Supabase token to this endpoint
- Backend verifies token, creates JWT, returns it
- NO database storage for auth (Supabase handles that)
"""

from fastapi import APIRouter, HTTPException, Request, status
import logging

from src.core.security import create_access_token, verify_supabase_token as verify_supabase
from src.schemas.auth import VerifySupabaseTokenRequest, AuthTokenResponse, UserResponse
from src.schemas.common import APIResponse, APIStatusCode

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/verify-supabase",
    response_model=APIResponse[AuthTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify Supabase token and get JWT",
)
async def verify_supabase_token(
    request: Request,
    auth_request: VerifySupabaseTokenRequest,
):
    """
    Verify Supabase token and exchange for backend JWT.

    Frontend authentication flow:
    1. User signs up/logs in via Supabase UI
    2. Supabase returns supabase_token (JWT) and stores user in Supabase database
    3. Frontend sends token to this endpoint
    4. Backend verifies token signature
    5. Creates backend JWT token from user data
    6. Returns JWT to frontend (not Supabase token)
    7. Frontend stores JWT in localStorage
    8. Frontend sends JWT with Authorization header for all requests

    Why no database storage here?
    - Supabase already stores user credentials and profile
    - We only need backend JWT for request validation
    - User table only needed for debate-specific data (skill level, match history, etc.)
    - Can be populated lazily when needed

    Args:
        request (Request): Framework context.
        auth_request (VerifySupabaseTokenRequest): Contains supabase_token from frontend.

    Raises:
        HTTPException(401): If Supabase token is invalid or expired.
        HTTPException(500): If JWT creation fails.
        RequestValidationError: If request payload validation fails.
    """
    try:
        # Step 1: Verify Supabase token
        supabase_user = verify_supabase(auth_request.supabase_token)
        
        if not supabase_user:
            logger.warning("Invalid Supabase token attempt")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Supabase token"
            )
        
        logger.info(f"Supabase token verified for user: {supabase_user.email}")
        
        # Step 2: Create backend JWT token (Supabase already stores user)
        access_token = create_access_token({
            "user_id": supabase_user.id,
            "email": supabase_user.email
        })
        
        logger.info(f"Backend JWT created for user: {supabase_user.email}")
        
        # Step 3: Return response
        response = APIResponse[AuthTokenResponse](
            status=APIStatusCode.SUCCESS,
            message="Authentication successful",
            data=AuthTokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=86400,  # 24 hours
                user=UserResponse(
                    id=supabase_user.id,
                    email=supabase_user.email,
                    display_name=supabase_user.display_name
                )
            )
        )
        
        logger.info(f"JWT token created for user: {supabase_user.email}")
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )
