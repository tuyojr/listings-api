#!/usr/bin/env bash
set -euo pipefail

SECRET_FILE="/run/secrets/listing_db_password"

if [ ! -f "$SECRET_FILE" ]; then
    echo "FATAL: Secret file $SECRET_FILE not found." >&2
    echo "Ensure docker-compose.yml mounts 'listing_db_password' onto this container." >&2
    exit 1
fi

LISTING_DB_PASSWORD="$(cat "$SECRET_FILE")"

if [ -z "$LISTING_DB_PASSWORD" ]; then
    echo "FATAL: Secret file $SECRET_FILE is empty." >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'listing_rw') THEN
            CREATE ROLE listing_rw WITH LOGIN PASSWORD '${LISTING_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE listings TO listing_rw;
    GRANT USAGE ON SCHEMA public TO listing_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO listing_rw;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO listing_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO listing_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO listing_rw;
EOSQL

echo "listing_rw role created."
