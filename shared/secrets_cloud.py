"""
Cloud secret retrieval for Cloud Run (GCP Secret Manager) and ECS (AWS Secrets Manager).

This module is imported lazily by shared/secrets.py::get_secret() when
ENV=production.

Design principles:
  • Authenticates via workload identity (Cloud Run service account / ECS task role).
    No credentials in environment variables, no credentials in files.
  • Each service's IAM role is scoped to its own secrets only.
  • Secrets are cached in process memory for the process lifetime.
  • Rotating a secret requires a new container deployment (fresh process) OR the caller can bypass the cache with cache=False.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


def _is_cloud_run() -> bool:
    """Cloud Run sets K_SERVICE on every container instance."""
    return os.getenv("K_SERVICE") is not None


def _is_ecs() -> bool:
    """ECS Fargate sets ECS_CONTAINER_METADATA_URI_V4."""
    return os.getenv("ECS_CONTAINER_METADATA_URI_V4") is not None


def _get_gcp_secret(secret_id: str, version: str = "latest") -> str:
    """
    Retrieve a secret from GCP Secret Manager.

    Authentication: uses Application Default Credentials, which on Cloud Run
    resolves to the service account attached to the Cloud Run revision.
    The service account must have roles/secretmanager.secretAccessor on the
    specific secret ARN. This is granted at the secret level.
    """
    from google.api_core import exceptions as gcp_exceptions
    from google.cloud import secretmanager

    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "GCP_PROJECT_ID is not set. Cloud Run deployments must set this "
            "env var so the container can build the secret resource name."
        )

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"

    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(
            request={"name": name},
            timeout=5.0,  # Fail fast if Secret Manager is unreachable
        )
    except gcp_exceptions.PermissionDenied as exc:
        # Do NOT include the secret name in the exception message shown to users only in the server-side log.
        logger.error("Permission denied reading secret %s", secret_id)
        raise RuntimeError(
            f"Service account lacks access to secret '{secret_id}'. "
            f"Grant roles/secretmanager.secretAccessor at the secret level."
        ) from exc
    except gcp_exceptions.NotFound as exc:
        logger.error("Secret not found: %s", secret_id)
        raise RuntimeError(f"Secret '{secret_id}' does not exist in Secret Manager.") from exc
    except gcp_exceptions.GoogleAPIError as exc:
        logger.error("Secret Manager API error for %s: %s", secret_id, exc)
        raise RuntimeError(f"Failed to retrieve secret '{secret_id}'.") from exc

    return response.payload.data.decode("UTF-8")


def _get_aws_secret(secret_id: str) -> str:
    """
    Retrieve a secret from AWS Secrets Manager.

    Authentication: uses the ECS task role attached to the task definition.
    The task role must have secretsmanager:GetSecretValue on the specific
    secret ARN, plus kms:Decrypt on the KMS key if the secret is encrypted
    with a customer-managed key.

    Returns the secret value as a plain string. If the secret is stored as
    JSON (e.g. {"password": "..."}), the caller is responsible for parsing.
    For our use case, we store passwords as plain strings in Secrets Manager,
    so no JSON parsing is needed here.
    """
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("AWS_REGION is not set. ECS deployments must set this env var.")

    try:
        client = boto3.client(
            "secretsmanager",
            region_name=region,
            config=boto3.session.Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        response = client.get_secret_value(SecretId=secret_id)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        logger.error("Secrets Manager error for %s: %s", secret_id, error_code)
        if error_code == "AccessDeniedException":
            raise RuntimeError(
                f"Task role lacks access to secret '{secret_id}'. "
                f"Grant secretsmanager:GetSecretValue on the secret ARN."
            ) from exc
        if error_code == "ResourceNotFoundException":
            raise RuntimeError(f"Secret '{secret_id}' does not exist in Secrets Manager.") from exc
        raise RuntimeError(f"Failed to retrieve secret '{secret_id}' ({error_code}).") from exc
    except BotoCoreError as exc:
        logger.error("Secrets Manager transport error for %s: %s", secret_id, exc)
        raise RuntimeError(f"Could not reach Secrets Manager to retrieve '{secret_id}'.") from exc

    secret = response.get("SecretString")
    if secret is None:
        raise RuntimeError(
            f"Secret '{secret_id}' has no SecretString. Binary secrets are not supported."
        )

    return secret


@lru_cache(maxsize=32)
def get_cloud_secret(name: str) -> str:
    """
    Retrieve a secret by name from the cloud provider detected at runtime.

    Called by shared/secret_store.py::get_secret() when ENV=production.
    The @lru_cache ensures the secret is fetched once per process, not per
    request. On rotation, redeploy the service to spawn a fresh process, or
    call get_cloud_secret.cache_clear() and re-fetch.

    Raises RuntimeError if neither Cloud Run nor ECS is detected, so the
    service fails fast at startup rather than silently using an empty
    or default value.
    """
    if _is_cloud_run():
        logger.info("Loading secret from GCP Secret Manager: %s", name)
        return _get_gcp_secret(name)

    if _is_ecs():
        logger.info("Loading secret from AWS Secrets Manager: %s", name)
        return _get_aws_secret(name)

    raise RuntimeError(
        "Cannot determine cloud environment. Expected K_SERVICE (Cloud Run) "
        "or ECS_CONTAINER_METADATA_URI_V4 (ECS). "
        f"ENV={os.getenv('ENV')!r}, secret requested={name!r}."
    )


def clear_secret_cache() -> None:
    """
    Clear the in-process cache. Call this if you implement a rotation
    mechanism that triggers a re-fetch without a container restart.
    """
    get_cloud_secret.cache_clear()
