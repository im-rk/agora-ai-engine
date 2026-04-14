from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os

security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        # Cryptographically extracts the user's UUID from the Supabase Token
        payload = jwt.decode(
            credentials.credentials, 
            os.getenv("SUPABASE_KEY"), 
            algorithms=["HS256"], 
            options={"verify_aud": False}
        )
        return payload["sub"] 
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
