import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas import (
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from shared.jwt_utils import validate_refresh_token
from shared.secret_store import get_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserRegister, db: DB) -> User:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: DB) -> TokenResponse:
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    # Constant-time comparison — always run verify even if user is None
    dummy_hash = "$argon2id$v=19$m=19456,t=2,p=1$" + "A" * 22 + "$" + "B" * 43
    hashed = user.hashed_password if user else dummy_hash
    valid = verify_password(body.password, hashed)

    if user is None or not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: DB) -> TokenResponse:
    secret = get_secret("jwt_secret_key")
    payload = validate_refresh_token(body.refresh_token, secret, settings.JWT_ALGORITHM)
    user_id = UUID(payload["sub"])

    token_hash = hash_refresh_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    user_result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    stored.revoked = True
    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(new_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, db: DB) -> None:
    token_hash = hash_refresh_token(body.refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True
        await db.commit()
