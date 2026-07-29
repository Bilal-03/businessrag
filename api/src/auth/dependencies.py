import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer(auto_error=False)
jwks_client = jwt.PyJWKClient(settings.jwks_url, cache_keys=True)

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Validate the Supabase JWT token and return the user_id.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            signing_key = settings.supabase_jwt_secret
        elif algorithm == "ES256":
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
        else:
            raise jwt.InvalidAlgorithmError("Unsupported token signing algorithm")

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience=settings.supabase_jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, jwt.PyJWKClientError):
        logger.warning(
            "invalid_authentication_token",
            extra={
                "event": "invalid_authentication_token",
                "request_id": getattr(request.state, "request_id", None),
                "path": request.url.path,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
