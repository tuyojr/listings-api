"""
Local JWT validation. Imported by the listings service (and any future service)
to validate tokens issued by the auth service WITHOUT calling the auth service.
The JWT secret is loaded from the secret store at startup.
"""

import logging

import jwt
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def decode_token(token: str, secret: str, algorithm: str = "HS256") -> dict:
    """
    Decode and validate a JWT. The algorithm is PINNED by the caller —
    never read from the token header. This prevents alg=none and
    algorithm-confusion attacks.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],  # PINNED
            options={
                "require": ["exp", "iat", "sub", "type"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return payload


def validate_access_token(token: str, secret: str, algorithm: str = "HS256") -> dict:
    """Validate an access token and ensure its type is 'access'."""
    payload = decode_token(token, secret, algorithm)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def validate_refresh_token(token: str, secret: str, algorithm: str = "HS256") -> dict:
    """Validate a refresh token and ensure its type is 'refresh'."""
    payload = decode_token(token, secret, algorithm)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
