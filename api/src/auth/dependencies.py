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
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token error: {type(e).__name__} - {str(e)}")
        # Try base64 decoding the secret if signature verification failed
        try:
            import base64
            decoded_secret = base64.b64decode(settings.supabase_jwt_secret)
            payload = jwt.decode(
                token,
                decoded_secret,
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
            detail="Invalid authentication credentials"
        )
