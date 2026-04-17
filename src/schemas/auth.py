"""
Authentication schemas - Request and Response DTOs.

All schemas for authentication endpoints in a single file.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional



class VerifySupabaseTokenRequest(BaseModel):
    """
    Request to verify Supabase token and get backend JWT.
    
    This is the ONLY auth endpoint backend needs.
    Frontend handles signup/login with Supabase.
    """
    supabase_token: str = Field(..., description="Supabase access token from frontend")
    
    class Config:
        json_schema_extra = {
            "example": {
                "supabase_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }



class UserResponse(BaseModel):
    """User data in auth response."""
    id: str
    email: str
    display_name: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "display_name": "John Doe"
            }
        }


class AuthTokenResponse(BaseModel):
    """Complete authentication response with JWT and user data."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds
    user: UserResponse
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "display_name": "John Doe"
                }
            }
        }


class CurrentUserData(BaseModel):
    """Current authenticated user data extracted from JWT token.
    
    Used by get_current_user dependency to return validated user data
    from JWT claims for protected routes.
    
    Attributes:
        user_id (str): UUID of authenticated user.
        email (str): Email of authenticated user.
    """
    user_id: str
    email: str


class SupabaseUserDTO(BaseModel):
    """User data extracted from Supabase token.
    
    Internal DTO used by security functions to parse Supabase JWT.
    NOT sent to frontend - used internally for type safety.
    
    Attributes:
        id (str): Supabase user ID.
        email (str): User email address.
        display_name (Optional[str]): User display name from metadata.
        metadata (Optional[dict]): Additional metadata from Supabase token.
    """
    id: str
    email: str
    display_name: Optional[str] = None
    metadata: Optional[dict] = None
