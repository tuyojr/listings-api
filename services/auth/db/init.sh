#!/usr/bin/env bash
set -euo pipefail

# SECRET_FILE="/run/secrets/auth_db_password"
RUNTIME_SECRET="/run/secrets/auth_db_password"

if [ ! -f "$RUNTIME_SECRET" ]; then
    echo "FATAL: Secret file $RUNTIME_SECRET not found." >&2
    # echo "Ensure docker-compose.yml mounts 'auth_db_password' onto this container." >&2
    exit 1
fi

# AUTH_DB_PASSWORD="$(cat "$SECRET_FILE")"
MIGRATE_PASSWORD="$(cat "$RUNTIME_SECRET")"
RUNTIME_PASSWORD="$(cat "$RUNTIME_SECRET")"

# if [ -z "$AUTH_DB_PASSWORD" ]; then
#     echo "FATAL: Secret file $SECRET_FILE is empty." >&2
#     exit 1
# fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'auth_migrate') THEN
            CREATE ROLE auth_migrate WITH LOGIN PASSWORD '${MIGRATE_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE auth TO auth_migrate;
    GRANT USAGE, CREATE ON SCHEMA public TO auth_migrate;
    ALTER SCHEMA public OWNER TO auth_migrate;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'auth_rw') THEN
            CREATE ROLE auth_rw WITH LOGIN PASSWORD '${RUNTIME_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE auth TO auth_rw;
    GRANT USAGE ON SCHEMA public TO auth_rw;
    -- Default privileges for objects created in future by auth_migrate:
    ALTER DEFAULT PRIVILEGES FOR ROLE auth_migrate IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO auth_rw;
    ALTER DEFAULT PRIVILEGES FOR ROLE auth_migrate IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO auth_rw;
EOSQL

echo "auth_rw role created."
