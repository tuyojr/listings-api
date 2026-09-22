#!/usr/bin/env bash
set -euo pipefail

# This script runs as part of the postgres entrypoint.
# The password secret is mounted at /run/secrets/auth_db_password.

AUTH_DB_PASSWORD="$(cat /run/secrets/auth_db_password)"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the least-privilege runtime role
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'auth_rw') THEN
            CREATE ROLE auth_rw WITH LOGIN PASSWORD '${AUTH_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE auth TO auth_rw;
    GRANT USAGE ON SCHEMA public TO auth_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO auth_rw;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO auth_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO auth_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO auth_rw;
EOSQL

echo "auth_rw role created."
