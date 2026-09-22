# Listings API

Isolated microservices for property listings. Each service owns its own database, runs in its own container, and communicates only through the gateway. Designed so a failure in one service does not affect the other.

## Architecture

```TEXT
                     Client (curl / browser)
                              │
                              ▼
              ┌────────────────────────────────┐
              │      api-gateway (nginx)        │
              │      • TLS termination          │
              │      • Rate limiting            │
              │      • Security headers         │
              │      • Dynamic upstream DNS     │
              └──────┬─────────────────┬────────┘
                     │                 │
        ┌────────────┘                 └────────────┐
        ▼                                            ▼
┌─────────────────┐                        ┌─────────────────┐
│  auth-service   │                        │listings-service │
│  :8000          │                        │  :8001          │
│  • register     │                        │  • CRUD listing │
│  • login        │                        │  • JWT verify   │
│  • refresh      │                        │  • RLS context  │
│  • issue JWT    │                        │                 │
└────────┬────────┘                        └────────┬────────┘
         │ auth-internal                            │ listing-internal
         ▼                                          ▼
┌─────────────────┐                        ┌─────────────────┐
│   auth-db       │                        │  listing-db     │
│   Postgres 18   │                        │  Postgres 18    │
│   • users       │                        │  • listings     │
│   • refresh_*   │                        │  • RLS: 4 pol.  │
└─────────────────┘                        └─────────────────┘
     internal network only                     internal network only
```

| Service | Purpose | Database | Port |
| --------- | --------- | ---------- | ------ |
| api-gateway | TLS, routing, rate limits | - | 80 |
| auth-service | Registration, login, JWT issuance | auth-db | 8000 (internal) |
| listings-service | Listing CRUD, RLS enforcement | listing-db | 8001 (internal) |
| auth-db | Users + refresh tokens | - | 5432 (internal) |
| listing-db | Listings | - | 5432 (internal) |

The services have **zero runtime coupling**. The listings service never calls the auth service. It validates JWTs locally using the shared signing key.

## Prerequisites

- Docker Engine 24+
- Docker Compose v2.20+
- `openssl` (for secret generation)
- `jq` (for the smoke tests below; optional)

## First-time setup

```bash
# 1. Generate local secrets (one-time)
chmod +x scripts/generate-secrets.sh
./scripts/generate-secrets.sh

# 2. Make the Postgres init scripts executable
chmod +x services/auth/db/init.sh services/listings/db/init.sh

# 3. Build and start everything
docker compose up --build -d

# 4. Apply database migrations
docker compose exec auth-service alembic upgrade head
docker compose exec listings-service alembic upgrade head

# 5. Verify
docker compose ps # all containers should be "healthy"
curl http://localhost/health # {"status":"ok"}
```

## Smoke test

```bash
# Register Amina
curl -s -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"amina@example.com","password":"Str0ng!Pass#2026"}' | jq

# Login
TOKEN=$(curl -s -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"amina@example.com","password":"Str0ng!Pass#2026"}' \
  | jq -r .access_token)

# Create a listing
curl -s -X POST http://localhost/api/v1/listings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"Modern 3BR House",
    "listing_type":"house",
    "address":"123 Main St",
    "city":"Ikeja",
    "state":"LA",
    "postal_code":"100125",
    "bedrooms":3,
    "bathrooms":2.0,
    "square_feet":1800,
    "price":2500000.00,
    "price_period":"monthly"
  }' | jq

# Read it back
curl -s http://localhost/api/v1/listings \
  -H "Authorization: Bearer $TOKEN" | jq
```

## Isolation test (RLS verification)

Proves that Row Level Security is enforced by PostgreSQL, not application code. Femi knows Amina's listing UUID but still cannot read it.

```bash
# Register Femi
curl -s -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"femi@example.com","password":"Str0ng!Pass#2026"}' > /dev/null

TOKEN2=$(curl -s -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"femi@example.com","password":"Str0ng!Pass#2026"}' \
  | jq -r .access_token)

# Femi lists all listings - expected: []
curl -s http://localhost/api/v1/listings \
  -H "Authorization: Bearer $TOKEN2" | jq

# Femi tries to read Amina's listing by known UUID - expected: 404
LISTING_ID=$(curl -s http://localhost/api/v1/listings \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

curl -s -o /dev/null -w "HTTP status: %{http_code}\n" \
  http://localhost/api/v1/listings/$LISTING_ID \
  -H "Authorization: Bearer $TOKEN2"
```

## Fault isolation

| Failure | Auth | Listings | User impact |
| --------- | :---: | :--------: | ------------- |
| Listings service down | OK | DOWN | Login works; listing pages return 503 |
| Auth service down | DOWN | OK | No new logins; existing JWTs still work until expiry |
| Auth DB down | DOWN | OK | Same as above |
| Listings DB down | OK | DOWN | Login works; listings return 503 |

Redeploying one service has zero impact on the other:

```bash
docker compose up -d --build --force-recreate listings-service
```

The health endpoint verifies database connectivity, so the platform's health probe correctly detects and reports outages. Test it:

```bash
docker compose stop auth-db
sleep 20
docker compose ps auth-service # expect "unhealthy"
docker compose start auth-db
sleep 20
docker compose ps auth-service # expect "healthy"
```

## Secrets

Secrets live in `secrets/` and are file-mounted into the containers at `/run/secrets/<name>`.

| Secret file | Consumed by | Purpose |
| ------------- | ------------- | --------- |
| `auth_db_password.txt` | auth-db (init), auth-service | Password for the `auth_rw` runtime role |
| `listing_db_password.txt` | listing-db (init), listings-service | Password for `listing_rw` |
| `auth_db_root_password.txt` | auth-db (init) | Postgres superuser password |
| `listing_db_root_password.txt` | listing-db (init) | Postgres superuser password |
| `jwt_secret_key.txt` | auth-service, listings-service | Shared HMAC signing key |

For local development, `auth_migrate` and `auth_rw` (and their listings equivalents) use the same password file. In the cloud they use separate secrets, but the code path is identical.

### File permissions

Secret files must be `0644` (readable by the Postgres container user, UID 999). The `generate-secrets.sh` script handles this.

## Database roles

Each database has two roles:

| Role | Purpose | Privileges |
| ------ | --------- | ----------- |
| `<svc>_migrate` | Owns schema objects, runs Alembic | `USAGE, CREATE` on schema, full DDL on owned tables |
| `<svc>_rw` | Runtime role used by the FastAPI app | `USAGE` on schema, `SELECT/INSERT/UPDATE/DELETE` on tables, no DDL |

The runtime role cannot create, alter, or drop tables even if compromised.

## Row Level Security

The `listings` table has RLS enabled with four policies, one per operation, all keyed on `current_setting('app.current_user_id')::uuid`.

```sql
-- SELECT
USING (owner_id = current_setting('app.current_user_id')::uuid)
-- INSERT
WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
-- UPDATE
USING (owner_id = current_setting('app.current_user_id')::uuid)
WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid)
-- DELETE
USING (owner_id = current_setting('app.current_user_id')::uuid)
```

The route handlers set the context per transaction:

```python
await set_rls_user(db, user_id) # SELECT set_config(..., true)
```

The setting is transaction-scoped (`is_local=true`), so it's automatically cleared when the transaction ends. Every new request sets it fresh.

Verify RLS is enabled:

```bash
docker compose exec listing-db psql -U postgres -d listings -c \
  "SELECT relname, relrowsecurity FROM pg_class WHERE relname='listings';"

docker compose exec listing-db psql -U postgres -d listings -c \
  "SELECT polname, polcmd FROM pg_policy WHERE polrelid = 'listings'::regclass;"
```

## Environment variables

Configured in `docker-compose.yml`. Non-secret values only.

| Variable | Values | Purpose |
| ---------- | -------- | --------- |
| `ENV` | `development` / `production` | Enables `/docs` in dev, selects secrets backend |
| `DB_SSL_MODE` | `require` / `disable` / `prefer` | `disable` for local Postgres; default `require` |
| `AUTH_DB_HOST`, `AUTH_DB_PORT`, `AUTH_DB_NAME`, `AUTH_DB_USER` | - | Connection metadata |
| `LISTING_DB_*` | - | Same for listings |
| `JWT_ALGORITHM` | `HS256` (pinned by validator) | Only HS256/384/512 allowed |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `ARGON2_*` | OWASP minimums | Password hashing cost parameters |

## Rebuilding after code changes

```bash
# Single service
docker compose up -d --build --force-recreate listings-service

# If you suspect stale layers
docker compose build --no-cache listings-service
docker compose up -d --force-recreate --no-deps listings-service
```

Docker Compose occasionally reports a fast build when it reuses a `COPY` layer. If a code change doesn't appear to take effect, verify the file inside the running container:

```bash
docker compose exec listings-service grep -n "some_new_code" /app/app/models.py
```

## Resetting the databases

The Postgres init scripts run **only on first initialization** of a fresh data volume. If you change an init script, a role, or the schema bootstrap, you must delete the volumes and let them re-initialize.

```bash
docker compose down
docker volume rm realestate-microservice_auth-pgdata
docker volume rm realestate-microservice_listing-pgdata
docker compose up --build -d
docker compose exec auth-service     alembic upgrade head
docker compose exec listings-service alembic upgrade head
```

## Production

The application code ships unchanged to the cloud. The differences:

| Local | Cloud |
| ------- | ------- |
| nginx gateway | Cloud Run ingress / ALB |
| `secrets/*.txt` mounted at `/run/secrets/` | Secret Manager / Secrets Manager |
| `auth-db` container | Cloud SQL / RDS in private VPC |
| Docker `internal: true` networks | VPC private subnets + security groups |
| `ENV=development` | `ENV=production` (disables `/docs`, activates cloud secrets) |
| `DB_SSL_MODE=disable` | Unset - defaults to `require` |

The secrets abstraction lives in `shared/secrets.py`. In `ENV=production`, `get_secret()` delegates to `shared/secrets_cloud.py`, which reads from GCP Secret Manager or AWS Secrets Manager depending on which environment is detected. No code changes are needed - only the environment.

## Security summary

| Layer | Control |
| ------- | --------- |
| Transport | TLS at gateway (production); HTTP locally |
| Auth | Argon2id password hashing; JWT algorithm pinned to HS256/384/512 |
| Auth | Short-lived access tokens (30 min); refresh tokens stored hashed |
| DB | SCRAM-SHA-256 auth; TLS required in production |
| DB | Least-privilege runtime role with no DDL |
| DB | Row Level Security enforced per user per operation |
| App | Pydantic validation on every request body |
| App | JWT algorithm pinned (prevents `alg=none` and confusion attacks) |
| App | `owner_id` sourced from JWT, never from request body |
| Gateway | Rate limiting (5/min auth, 60/min API) |
| Gateway | Security headers (HSTS, CSP, XFO, XSS, etc.) |
| Secrets | File-mounted, per-service grants, never in env vars |
| Network | Database containers on isolated internal networks |
| Container | Non-root user; no shell in the production image |
