"""
One-time bootstrap for the app-level Postgres roles (rw + migrate) that
services/*/db/init.sh normally creates via docker-entrypoint-initdb.d in
local Docker Compose. RDS has no equivalent hook, so on a fresh RDS
instance these roles don't exist until this is run once.

Run as a one-off ECS Fargate task (modules/db_bootstrap in the infra repo)
via the db-bootstrap.yml workflow, which passes RDS_MASTER_SECRET_ARN and
the usual AUTH_DB_*/LISTING_DB_* env vars through the task definition:

    python3 scripts/bootstrap_db_roles.py auth
    python3 scripts/bootstrap_db_roles.py listings

RDS_MASTER_SECRET_ARN just identifies the RDS-managed master "postgres"
secret (aws_db_instance.main has manage_master_user_password = true) - it
is not the password itself. This task's IAM role is the only role allowed
to read it (see modules/iam's db_bootstrap_task role); the always-running
app services cannot. The actual password is fetched and decrypted here,
at runtime, the same way shared/secrets_cloud.py fetches every other
secret - never passed in as plaintext.

The rw/migrate role passwords come from the same Secrets Manager secrets
the app already reads at startup (shared/secret_store.py), so they stay
in sync with whatever sync-secrets-dev.yml last pushed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg
import boto3

from shared.secret_store import get_secret

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SERVICES = {
    "auth": {
        "host_env": "AUTH_DB_HOST",
        "port_env": "AUTH_DB_PORT",
        "name_env": "AUTH_DB_NAME",
        "rw_user_env": "AUTH_DB_USER",
        "migrate_user_env": "AUTH_DB_MIGRATE_USER",
        "rw_password_secret": "auth_db_password",  # pragma: allowlist secret
        "migrate_password_secret": "auth_db_migrate_password",  # pragma: allowlist secret
    },
    "listings": {
        "host_env": "LISTING_DB_HOST",
        "port_env": "LISTING_DB_PORT",
        "name_env": "LISTING_DB_NAME",
        "rw_user_env": "LISTING_DB_USER",
        "migrate_user_env": "LISTING_DB_MIGRATE_USER",
        "rw_password_secret": "listing_db_password",  # pragma: allowlist secret
        "migrate_password_secret": "listing_db_migrate_password",  # pragma: allowlist secret
    },
}


def _escape_literal(value: str) -> str:
    """Escape a value for use inside a single-quoted SQL string literal."""
    return value.replace("'", "''")


def _get_master_password(secret_arn: str) -> str:
    """Fetch and decrypt the RDS-managed master secret via this task's IAM role."""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])["password"]


async def bootstrap(service: str) -> None:
    cfg = SERVICES[service]
    master_password = _get_master_password(os.environ["RDS_MASTER_SECRET_ARN"])

    host = os.environ[cfg["host_env"]]
    port = int(os.environ.get(cfg["port_env"], "5432"))
    dbname = os.environ[cfg["name_env"]]
    rw_user = os.environ[cfg["rw_user_env"]]
    migrate_user = os.environ[cfg["migrate_user_env"]]
    rw_password = _escape_literal(get_secret(cfg["rw_password_secret"]))
    migrate_password = _escape_literal(get_secret(cfg["migrate_password_secret"]))

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=dbname,
        user="postgres",
        password=master_password,
        ssl=True,
    )
    try:
        await conn.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{migrate_user}') THEN
                    CREATE ROLE {migrate_user} WITH LOGIN PASSWORD '{migrate_password}';
                END IF;
            END
            $$;
        """)
        await conn.execute(f"GRANT CONNECT ON DATABASE {dbname} TO {migrate_user};")
        await conn.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {migrate_user};")
        await conn.execute(f"ALTER SCHEMA public OWNER TO {migrate_user};")

        await conn.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{rw_user}') THEN
                    CREATE ROLE {rw_user} WITH LOGIN PASSWORD '{rw_password}';
                END IF;
            END
            $$;
        """)
        await conn.execute(f"GRANT CONNECT ON DATABASE {dbname} TO {rw_user};")
        await conn.execute(f"GRANT USAGE ON SCHEMA public TO {rw_user};")
        await conn.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {migrate_user} IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rw_user};"
        )
        await conn.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {migrate_user} IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {rw_user};"
        )
    finally:
        await conn.close()

    logger.info("%s: %s and %s roles ready.", service, migrate_user, rw_user)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SERVICES:
        logger.error("usage: python3 %s <auth|listings>", sys.argv[0])
        sys.exit(1)
    asyncio.run(bootstrap(sys.argv[1]))
