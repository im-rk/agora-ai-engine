"""
Security utilities.

Handles:
- Password hashing
- JWT token creation and verification
- Supabase token verification
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from src.schemas.auth import SupabaseUserDTO

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class TokenData(BaseModel):
    """Data contained in JWT token."""
    user_id: str
    email: str


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Data to encode (user_id, email, etc.)
        expires_delta: Custom expiration time
    
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    # Set expiration
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    
    # Encode JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """
    Verify JWT token and extract data.
    
    Args:
        token: JWT token string
    
    Returns:
        TokenData if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        
        if user_id is None or email is None:
            return None
        
        return TokenData(user_id=user_id, email=email)
    except JWTError:
        return None


def verify_supabase_token(token: str) -> Optional[SupabaseUserDTO]:
    """
    Verify Supabase token and extract user data.
    
    Args:
        token: Supabase access token (JWT)
    
    Returns:
        SupabaseUserDTO if valid, None if invalid
    
    Note:
        Supabase tokens are JWTs that can be decoded.
        In production, verify the signature with Supabase public key.
        For now, we decode without verification and extract user data.
    """
    try:
        # Decode JWT without verification (trusting Supabase)
        # In production, verify with Supabase public key
        payload = jwt.decode(token, options={"verify_signature": False})
        
        # Extract user data from Supabase token
        user_id = payload.get("sub")  # Supabase uses 'sub' for user ID
        email = payload.get("email")
        
        if not user_id or not email:
            return None
        
        # Get user metadata if available
        user_metadata = payload.get("user_metadata", {})
        display_name = user_metadata.get("display_name")
        
        return SupabaseUserDTO(
            id=user_id,
            email=email,
            display_name=display_name,
            metadata=user_metadata
        )
    
    except JWTError:
        return None
    except Exception:
        return None

