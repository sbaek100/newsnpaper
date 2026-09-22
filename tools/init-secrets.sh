#!/bin/bash
set -e

SECRETS_DIR="secrets"

mkdir -p "$SECRETS_DIR"

create_secret() {
    local file="$SECRETS_DIR/$1"
    local default_val="$2"
    
    if [ ! -f "$file" ]; then
        if [ "$default_val" = "RANDOM" ]; then
            head -c 32 /dev/urandom | base64 > "$file"
        else
            echo -n "$default_val" > "$file"
        fi
        chmod 0600 "$file"
        echo "Created $file"
    else
        echo "Skipped $file (already exists)"
    fi
}

create_secret "db_password" "RANDOM"
create_secret "jwt_secret" "RANDOM"
create_secret "naver_client_secret" ""
create_secret "admin_initial_password" ""

echo
echo "Secrets initialization complete."
echo "Please manually edit secrets/naver_client_secret and secrets/admin_initial_password with appropriate values."
