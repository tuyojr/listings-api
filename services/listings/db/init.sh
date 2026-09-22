#!/usr/bin/env bash
set -euo pipefail

# SECRET_FILE="/run/secrets/listing_db_password"
RUNTIME_SECRET="/run/secrets/listing_db_password"

if [ ! -f "$RUNTIME_SECRET" ]; then
    echo "FATAL: Secret file $RUNTIME_SECRET not found." >&2
    # echo "Ensure docker-compose.yml mounts 'listing_db_password' onto this container." >&2
    exit 1
fi

# LISTING_DB_PASSWORD="$(cat "$SECRET_FILE")"
MIGRATE_PASSWORD="$(cat "$RUNTIME_SECRET")"
RUNTIME_PASSWORD="$(cat "$RUNTIME_SECRET")"

# if [ -z "$LISTING_DB_PASSWORD" ]; then
#     echo "FATAL: Secret file $SECRET_FILE is empty." >&2
#     exit 1
# fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'listing_migrate') THEN
            CREATE ROLE listing_migrate WITH LOGIN PASSWORD '${MIGRATE_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE listings TO listing_migrate;
    GRANT USAGE, CREATE ON SCHEMA public TO listing_migrate;
    ALTER SCHEMA public OWNER TO listing_migrate;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'listing_rw') THEN
            CREATE ROLE listing_rw WITH LOGIN PASSWORD '${RUNTIME_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE listings TO listing_rw;
    GRANT USAGE ON SCHEMA public TO listing_rw;
    -- Default privileges for objects created in future by listing_migrate:
    ALTER DEFAULT PRIVILEGES FOR ROLE listing_migrate IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO listing_rw;
    ALTER DEFAULT PRIVILEGES FOR ROLE listing_migrate IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO listing_rw;
EOSQL

echo "listing_rw role created."
