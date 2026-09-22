#!/usr/bin/env bash
# Generate cryptographically strong secrets for local development.
# Run this ONCE. Secrets persist until you delete the secrets/ directory.
set -euo pipefail

SECRETS_DIR="$(dirname "$0")/../secrets"
mkdir -p "$SECRETS_DIR"

generate() {
    local name="$1"
    local file="$SECRETS_DIR/$name.txt"
    if [ -f "$file" ]; then
        echo "  ✓ $name.txt already exists — skipping"
        return
    fi
    openssl rand -base64 48 | tr -d '\n' > "$file"
    chmod 644 "$file"
    echo "  ✓ Generated $name.txt"
}

echo "Generating secrets in $SECRETS_DIR"
generate auth_db_password
generate listing_db_password
generate auth_db_root_password
generate listing_db_root_password
generate jwt_secret_key

echo ""
echo "Done. Secrets are gitignored and will not be committed."
