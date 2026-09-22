#!/usr/bin/env bash
set -euo pipefail

SECRET_FILE="/run/secrets/auth_db_password"

if [ ! -f "$SECRET_FILE" ]; then
    echo "FATAL: Secret file $SECRET_FILE not found." >&2
    echo "Ensure docker-compose.yml mounts 'auth_db_password' onto this container." >&2
    exit 1
fi

AUTH_DB_PASSWORD="$(cat "$SECRET_FILE")"

if [ -z "$AUTH_DB_PASSWORD" ]; then
    echo "FATAL: Secret file $SECRET_FILE is empty." >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
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
