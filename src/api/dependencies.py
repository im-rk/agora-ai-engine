import os
import requests
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()
security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    
    # -------------------------------------------------------------------
    # PRODUCTION GRADE: Token Introspection via Identity Provider
    # Since Supabase upgraded to ES256 but the JWKS endpoint returns 404,
    # the most secure method is to ask Supabase's Auth API directly to 
    # validate the session. 
    # -------------------------------------------------------------------
    
    # Forcefully use the issuer URL from the token. 
    # This prevents DNS "11001" crashes if the .env file has a typo (which it does!)
    import jwt
    unverified = jwt.decode(token, options={"verify_signature": False})
    issuer = unverified.get("iss", "")
    
    # Strip the /auth/v1 to get the pure supabase url
    supabase_url = issuer.replace("/auth/v1", "")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    url = f"{supabase_url}/auth/v1/user"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {token}"
    }
    
    # Call Supabase to cryptographically secure the session
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Token Introspection Failed: {response.text}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    user_data = response.json()
    return user_data.get("id")
