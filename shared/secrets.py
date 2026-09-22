"""
Secrets loading for local (Docker secrets) and cloud (Secret Manager / Secrets Manager).

Local development:
    Docker Compose mounts each secret file at /run/secrets/<name>.
    The file is read at startup and the value is held in process memory only.

Cloud (Cloud Run / ECS):
    Override get_secret() to call the cloud provider's secret manager API
    using the workload identity. The function signature stays the same.
"""
import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

SECRETS_DIR = "/run/secrets"


def _read_file_secret(name: str) -> str:
    """Read a Docker secret from /run/secrets/<name>."""
    path = os.path.join(SECRETS_DIR, name)
    if not os.path.isfile(path):
        raise RuntimeError(
            f"Secret file not found: {path}. "
            f"Run scripts/generate-secrets.sh and ensure docker-compose.yml "
            f"grants this service access to the secret."
        )
    with open(path, "r", encoding="utf-8") as f:
        value = f.read().strip()
    if not value:
        raise RuntimeError(f"Secret file is empty: {path}")
    return value


@lru_cache(maxsize=32)
def get_secret(name: str) -> str:
    """
    Retrieve a secret by name.

    Local:  reads /run/secrets/<name>
    Cloud:  replace the body with a Secret Manager / Secrets Manager call.
            See shared/secrets_cloud.py for the cloud implementation.

    Cached in memory for the process lifetime. When the platform redeploys
    the container after rotation, a fresh process fetches the new value.
    """
    if os.getenv("ENV") == "production":
        # Cloud path — import lazily so boto3/google-cloud aren't needed locally
        from shared.secrets_cloud import get_cloud_secret
        return get_cloud_secret(name)

    logger.info("Loading secret from file: %s", name)
    return _read_file_secret(name)


def build_database_url(
    *,
    host_env: str,
    port_env: str,
    name_env: str,
    user_env: str,
    password_secret: str,
) -> str:
    """
    Build a PostgreSQL async URL from non-sensitive env vars + a secret password.
    The password is retrieved at runtime from the secret store.
    """
    host = os.environ[host_env]
    port = os.environ.get(port_env, "5432")
    dbname = os.environ[name_env]
    user = os.environ[user_env]
    password = get_secret(password_secret)

    return (
        f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
        f"?ssl=require"
    )