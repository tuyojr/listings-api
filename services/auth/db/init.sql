-- Runs as the postgres superuser on first container start.
-- Creates the database schema and extensions.
-- Role creation is handled by init.sh.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Revoke default public schema creation
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
