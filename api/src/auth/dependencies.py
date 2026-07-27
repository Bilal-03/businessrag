import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Validate the Supabase JWT token and return the user_id.
    """
    token = credentials.credentials
    try:
        # Supabase JWTs are signed with the JWT Secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject (user id)"
            )
        return user_id
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token has expired: {str(e)}"
        )
    except jwt.InvalidTokenError as e:
        # Check if the token is valid but failed due to ES256/algorithm mismatch
        # We can securely verify the token using the Supabase API
        try:
            import httpx
            headers = {
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {token}"
            }
            # Make a synchronous request to the Supabase API
            with httpx.Client() as client:
                response = client.get(
                    f"{settings.supabase_url}/auth/v1/user",
                    headers=headers,
                    timeout=5.0
                )
            if response.status_code == 200:
                user_data = response.json()
                return user_data.get("id")
            else:
                logger.error(f"Supabase API token verification failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials (API fallback failed)"
                )
        except Exception as fallback_e:
            logger.error(f"Fallback verification failed: {type(fallback_e).__name__} - {str(fallback_e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except Exception as e:
        logger.error(f"Unexpected token error: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials. Error: {str(e)}"
        )
