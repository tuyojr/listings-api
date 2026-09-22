import logging
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy import text

from shared.secrets import build_database_url
from app.config import settings

from fastapi import Request

logger = logging.getLogger(__name__)


def build_listings_database_url() -> str:
    return build_database_url(
        host_env="LISTING_DB_HOST",
        port_env="LISTING_DB_PORT",
        name_env="LISTING_DB_NAME",
        user_env="LISTING_DB_USER",
        password_secret="listing_db_password",
    )


def build_listing_migration_url() -> str:
    """Migration URL that's used only by Alembic. Has DDL privileges."""
    return build_database_url(
        host_env="LISTING_DB_HOST",
        port_env="LISTING_DB_PORT",
        name_env="LISTING_DB_NAME",
        user_env="LISTING_DB_MIGRATE_USER",
        password_secret="listing_db_migrate_password",
    )


def create_engine_and_session(database_url: str):
    engine = create_async_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
        future=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


async def get_db(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def set_rls_user(session: AsyncSession, user_id):
    """
    Set the current user ID for RLS policies within this transaction.
    Uses set_config with is_local=true so the setting is transaction-scoped
    and automatically reset when the transaction ends.
    """
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
