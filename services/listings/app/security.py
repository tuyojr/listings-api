"""
The listings service validates tokens locally using the shared JWT secret.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from shared.jwt_utils import validate_access_token
from shared.secret_store import get_secret

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = get_secret("jwt_secret_key")
    payload = validate_access_token(credentials.credentials, secret, settings.JWT_ALGORITHM)
    return UUID(payload["sub"])
