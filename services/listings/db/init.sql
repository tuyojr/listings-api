-- Runs as the postgres superuser on first container start.
-- Creates extensions only.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
