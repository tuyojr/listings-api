import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import settings
from shared.secret_store import get_secret

# ─── Password hashing ───
_password_hasher = PasswordHash(
    hashers=[
        Argon2Hasher(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST,
            parallelism=settings.ARGON2_PARALLELISM,
        )
    ]
)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hasher.verify(plain, hashed)


def _get_jwt_secret() -> str:
    """Load the JWT secret from the secret store."""
    return get_secret("jwt_secret_key")


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def hash_refresh_token(token: str) -> str:
    """Store a hash of the refresh token, never the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
