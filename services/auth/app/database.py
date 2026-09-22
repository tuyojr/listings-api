"""
Async engine and session factory. The engine is created ONCE at startup
from a database URL that is assembled from env vars + a secret at runtime.
The URL is never stored in an environment variable or logged.
"""

import logging

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.secret_store import build_database_url

logger = logging.getLogger(__name__)


def build_auth_database_url() -> str:
    """Assemble the database URL from env vars + the secret password."""
    return build_database_url(
        host_env="AUTH_DB_HOST",
        port_env="AUTH_DB_PORT",
        name_env="AUTH_DB_NAME",
        user_env="AUTH_DB_USER",
        password_secret="auth_db_password",
    )


def build_auth_migration_url() -> str:
    """Migration URL that's used only by Alembic. Has DDL privileges."""
    return build_database_url(
        host_env="AUTH_DB_HOST",
        port_env="AUTH_DB_PORT",
        name_env="AUTH_DB_NAME",
        user_env="AUTH_DB_MIGRATE_USER",
        password_secret="auth_db_migrate_password",
    )


def create_engine_and_session(database_url: str):
    """
    Create the async engine and session factory.
    echo is hardcoded False. SQLAlchemy would otherwise log parameter
    values (including password hashes) into application logs.
    """
    engine = create_async_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
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
    """FastAPI dependency: yields a session from the app-level factory."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session
