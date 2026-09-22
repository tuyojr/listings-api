# Real Estate Microservices

Isolated microservices for real estate listings, with per-service databases, file-mounted secrets, and local Docker Compose development.

## Architecture

```TXT
Client → api-gateway (nginx) → auth-service      → auth-db
                             → listings-service  → listing-db
```

Each service has its own database. Databases are on internal Docker networks with no host access. Secrets are file-mounted, never environment variables.

## Prerequisites

- Docker Engine 24+
- Docker Compose v2.20+

## Quick start

```bash
# 1. Generate local secrets (run once)
chmod +x scripts/generate-secrets.sh
./scripts/generate-secrets.sh

# 2. Make the DB init scripts executable
chmod +x services/auth/db/init.sh services/listings/db/init.sh

# 3. Build and start
docker compose up --build -d

# 4. Apply database migrations
docker compose exec auth-service alembic upgrade head
docker compose exec listings-service alembic upgrade head

# 5. Verify
curl http://localhost/health
```

## Testing the API

```bash
# Register
curl -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Str0ng!Pass#2026"}'

# Login
TOKEN=$(curl -s -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Str0ng!Pass#2026"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a listing
curl -X POST http://localhost/api/v1/listings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Modern 3BR House",
    "listing_type": "house",
    "address": "123 Main St",
    "city": "Ikeja",
    "state": "LA",
    "postal_code": "100271",
    "bedrooms": 3,
    "bathrooms": 2.0,
    "square_feet": 1800,
    "price": 2500000.00,
    "price_period": "monthly"
  }'

# List listings
curl http://localhost/api/v1/listings?city=Austin \
  -H "Authorization: Bearer $TOKEN"
```

## Fault isolation

| Failure | Auth | Listings | Impact |
| --------- | :---: | :--------: | -------- |
| Listings service down | ✅ | ❌ | Login works; listings return 503 |
| Auth service down | ❌ | ✅ | No new logins; existing tokens still work |
| Auth DB down | ❌ | ✅ | Same as above |
| Listings DB down | ✅ | ❌ | Login works; listings return 503 |

Redeploying one service has zero impact on the other:

```bash
docker compose up -d --build listings-service
```

## Secrets

- Local secrets live in `secrets/` (gitignored).
- Each service is granted access only to the secrets it needs.
- The application reads secrets from `/run/secrets/<name>` at startup.
- In the cloud, replace `shared/secrets.py::get_secret` with a call to Secret Manager (GCP) or Secrets Manager (AWS) using the workload identity. The application code path is identical.

## Production notes

- Replace the nginx gateway with Cloud Run/ECS ingress or an API Gateway.
- Replace file-mounted secrets with Secret Manager / Secrets Manager.
- Enable TLS 1.3 at the ingress.
- Set `ENV=production` to disable `/docs` and enable the cloud secret path.
- Use `docker compose -f docker-compose.yml -f docker-compose.prod.yml` for production overrides.
