#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$PROJECT_ROOT/.ptmm-install"

load_state() {
    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        if [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
            printf -v "$key" '%s' "$value"
        fi
    done < "$STATE_FILE"
}

echo "PT Media Manager Installer"

is_deploy_mode() {
    [[ "$MODE" == "internal" || "$MODE" == "public" ]]
}

# Step 1: Reuse previous config?

REUSE_CONFIG=false
if [[ -f "$STATE_FILE" ]]; then
    load_state

    echo ""
    echo "Found previous install config ($STATE_FILE):"
    echo "  Mode: $MODE"
    if is_deploy_mode; then
        echo "  Deploy user: ${DEPLOY_USER:-$(whoami)}"
        echo "  Backend port: ${BACKEND_PORT:-8000}"
        echo "  Frontend root: ${FRONTEND_ROOT:-/var/www/ptmm}"
    fi
    if [[ "$MODE" == "internal" ]]; then
        echo "  HTTP port: ${HTTP_PORT:-8080}"
    fi
    if [[ "$MODE" == "public" ]]; then
        echo "  Domain: $DOMAIN"
        echo "  HTTPS port: ${HTTPS_PORT:-443}"
    fi
    echo ""
    read -rp "Reuse this configuration and reinstall? [Y/n]: " REUSE_CHOICE
    REUSE_CHOICE="${REUSE_CHOICE:-Y}"
    if [[ "$REUSE_CHOICE" =~ ^[Yy]$ ]]; then
        REUSE_CONFIG=true
    fi
fi

if [[ "$REUSE_CONFIG" == false ]]; then

    # Step 1b: Select mode

    echo ""
    echo "Deploy mode:"
    echo "  1) Internal    (HTTP + private network access, no auth)"
    echo "  2) Public      (HTTPS + JWT auth)"
    echo ""
    read -rp "Select [1/2]: " MODE_CHOICE

    case "$MODE_CHOICE" in
        1) MODE="internal" ;;
        2) MODE="public" ;;
        *)
            echo "Invalid choice. Aborting."
            exit 1
            ;;
    esac
fi

# Step 2: Dependency check

echo ""
echo "Checking dependencies..."

MISSING_DEPS=()

if ! command -v uv &>/dev/null; then
    MISSING_DEPS+=("uv  ->  https://docs.astral.sh/uv/getting-started/installation/")
fi

if ! command -v npm &>/dev/null; then
    MISSING_DEPS+=("npm  ->  https://nodejs.org/")
fi

if is_deploy_mode; then
    if ! command -v systemctl &>/dev/null; then
        MISSING_DEPS+=("systemctl")
    fi
    if ! command -v nginx &>/dev/null; then
        MISSING_DEPS+=("nginx")
    fi
fi

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo ""
    echo "Error: missing required dependencies:"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "  - $dep"
    done
    exit 1
fi

echo "All dependencies found."

# Step 3: Collect config

if [[ "$REUSE_CONFIG" == false ]]; then
    echo ""
    echo "Configuration:"
    echo "(Press Enter to accept the default shown in parentheses)"
    echo ""

    read -rp "TMDB API key (required): " TMDB_API_KEY
    if [[ -z "$TMDB_API_KEY" ]]; then
        echo "Error: TMDB API key cannot be empty."
        exit 1
    fi

    DEPLOY_USER=""
    DOMAIN=""
    HTTP_PORT=""
    HTTPS_PORT=""
    BACKEND_PORT=""
    FRONTEND_ROOT=""
    AUTH_USERNAME=""
    AUTH_PASSWORD_HASH=""
    JWT_SECRET=""

    if is_deploy_mode; then
        read -rp "Deploy user (default: $(whoami)): " DEPLOY_USER
        DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"

        read -rp "Backend port (default: 8000): " BACKEND_PORT
        BACKEND_PORT="${BACKEND_PORT:-8000}"

        read -rp "Frontend static directory (default: /var/www/ptmm): " FRONTEND_ROOT
        FRONTEND_ROOT="${FRONTEND_ROOT:-/var/www/ptmm}"
    fi

    if [[ "$MODE" == "internal" ]]; then
        read -rp "HTTP port (default: 8080): " HTTP_PORT
        HTTP_PORT="${HTTP_PORT:-8080}"
    fi

    if [[ "$MODE" == "public" ]]; then
        read -rp "Domain (e.g. ptmm.example.com): " DOMAIN

        read -rp "HTTPS port (default: 443): " HTTPS_PORT
        HTTPS_PORT="${HTTPS_PORT:-443}"

        echo ""
        echo "SSL certificate paths:"
        DEFAULT_CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
        DEFAULT_KEY="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
        read -rp "  Certificate (fullchain) (default: $DEFAULT_CERT): " SSL_CERT
        SSL_CERT="${SSL_CERT:-$DEFAULT_CERT}"
        read -rp "  Private key (default: $DEFAULT_KEY): " SSL_KEY
        SSL_KEY="${SSL_KEY:-$DEFAULT_KEY}"

        echo ""
        echo "Auth setup:"
        read -rp "  Username (default: admin): " AUTH_USERNAME
        AUTH_USERNAME="${AUTH_USERNAME:-admin}"
        read -s -rp "  Password: " AUTH_PASSWORD_PLAIN
        echo ""
        if [[ -z "$AUTH_PASSWORD_PLAIN" ]]; then
            echo "Error: password cannot be empty."
            exit 1
        fi

        echo "Generating password hash and JWT secret..."
        AUTH_PASSWORD_HASH=$(uv run --directory "$PROJECT_ROOT/backend" --frozen python -c "import bcrypt; print(bcrypt.hashpw(b'${AUTH_PASSWORD_PLAIN}', bcrypt.gensalt()).decode())")
        JWT_SECRET=$(uv run --directory "$PROJECT_ROOT/backend" --frozen python -c "import secrets; print(secrets.token_hex(32))")
    fi
else
    echo ""
    echo "Reusing saved configuration."
    if is_deploy_mode; then
        DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"
        BACKEND_PORT="${BACKEND_PORT:-8000}"
        FRONTEND_ROOT="${FRONTEND_ROOT:-/var/www/ptmm}"
    fi
    if [[ "$MODE" == "internal" ]]; then
        HTTP_PORT="${HTTP_PORT:-8080}"
    fi
    if [[ "$MODE" == "public" ]]; then
        HTTPS_PORT="${HTTPS_PORT:-443}"
    fi
fi

if is_deploy_mode; then
    case "$FRONTEND_ROOT" in
        /*) ;;
        *)
            echo "Error: frontend static directory must be an absolute path."
            exit 1
            ;;
    esac
    if [[ "$FRONTEND_ROOT" == "/" ]]; then
        echo "Error: frontend static directory cannot be /."
        exit 1
    fi
fi

# Step 4: Build frontend

echo ""
echo "[1/4] Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm ci
if is_deploy_mode; then
    VITE_API_BASE=/api npm run build
else
    npm run build
fi
rm -rf node_modules
echo "node_modules removed after build."

# Step 5: Write backend .env

echo ""
echo "[2/4] Writing backend config..."
{
    echo "TMDB_API_KEY=$TMDB_API_KEY"
    if [[ "$MODE" == "public" ]]; then
        echo "AUTH_ENABLED=true"
        echo "AUTH_USERNAME=$AUTH_USERNAME"
        echo "AUTH_PASSWORD_HASH=$AUTH_PASSWORD_HASH"
        echo "JWT_SECRET=$JWT_SECRET"
    else
        echo "AUTH_ENABLED=false"
    fi
} > "$PROJECT_ROOT/backend/.env"
chmod 600 "$PROJECT_ROOT/backend/.env"

# Step 6: Sync Python dependencies

echo ""
echo "[3/4] Syncing Python dependencies..."
uv sync --no-dev --frozen --directory "$PROJECT_ROOT/backend"

# Step 7: Install system services

echo ""
echo "[4/4] Installing system services..."

if is_deploy_mode; then
    UV_BIN="$(command -v uv)"

    echo "Publishing frontend to $FRONTEND_ROOT..."
    sudo mkdir -p "$FRONTEND_ROOT"
    sudo find "$FRONTEND_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    sudo cp -a "$PROJECT_ROOT/frontend/dist/." "$FRONTEND_ROOT/"
    sudo chown -R root:root "$FRONTEND_ROOT"
    sudo chmod -R a+rX "$FRONTEND_ROOT"

    sed \
        -e "s|\${DEPLOY_USER}|$DEPLOY_USER|g" \
        -e "s|\${PROJECT_ROOT}|$PROJECT_ROOT|g" \
        -e "s|\${UV_PATH}|$UV_BIN|g" \
        -e "s|\${BACKEND_PORT}|$BACKEND_PORT|g" \
        < "$PROJECT_ROOT/systemd/ptmm.service" \
        | sudo tee /etc/systemd/system/ptmm.service > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable ptmm
    sudo systemctl restart ptmm
    echo "Backend service started."

    sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    if [[ "$MODE" == "public" ]]; then
        sed \
            -e "s|\${DOMAIN}|$DOMAIN|g" \
            -e "s|\${FRONTEND_ROOT}|$FRONTEND_ROOT|g" \
            -e "s|\${SSL_CERT}|$SSL_CERT|g" \
            -e "s|\${SSL_KEY}|$SSL_KEY|g" \
            -e "s|\${HTTPS_PORT}|$HTTPS_PORT|g" \
            -e "s|\${BACKEND_PORT}|$BACKEND_PORT|g" \
            < "$PROJECT_ROOT/nginx/ptmm.conf" \
            | sudo tee /etc/nginx/sites-available/ptmm > /dev/null
    else
        sed \
            -e "s|\${HTTP_PORT}|$HTTP_PORT|g" \
            -e "s|\${FRONTEND_ROOT}|$FRONTEND_ROOT|g" \
            -e "s|\${BACKEND_PORT}|$BACKEND_PORT|g" \
            < "$PROJECT_ROOT/nginx/ptmm-internal.conf" \
            | sudo tee /etc/nginx/sites-available/ptmm > /dev/null
    fi
    sudo ln -sf /etc/nginx/sites-available/ptmm /etc/nginx/sites-enabled/ptmm
    if ! sudo nginx -t; then
        echo "Error: nginx config test failed."
        exit 1
    fi
    sudo systemctl reload nginx
    echo "Nginx config installed."
    echo ""
    echo "Frontend files served from: $FRONTEND_ROOT"
else
    echo "Unknown mode: $MODE"
    exit 1
fi

# Write state file (contains secrets, keep permissions tight)

{
    echo "MODE=$MODE"
    echo "TMDB_API_KEY=$TMDB_API_KEY"
    if is_deploy_mode; then
        echo "DEPLOY_USER=$DEPLOY_USER"
        echo "BACKEND_PORT=$BACKEND_PORT"
        echo "FRONTEND_ROOT=$FRONTEND_ROOT"
    fi
    if [[ "$MODE" == "internal" ]]; then
        echo "HTTP_PORT=$HTTP_PORT"
    fi
    if [[ "$MODE" == "public" ]]; then
        echo "DOMAIN=$DOMAIN"
        echo "HTTPS_PORT=$HTTPS_PORT"
        echo "SSL_CERT=$SSL_CERT"
        echo "SSL_KEY=$SSL_KEY"
        echo "AUTH_USERNAME=$AUTH_USERNAME"
        echo "AUTH_PASSWORD_HASH=$AUTH_PASSWORD_HASH"
        echo "JWT_SECRET=$JWT_SECRET"
    fi
} > "$STATE_FILE"
chmod 600 "$STATE_FILE"

echo ""
if [[ "$MODE" == "public" ]]; then
    echo "Done! Visit https://$DOMAIN"
else
    echo "Done! Visit http://<NAS-IP>:$HTTP_PORT"
fi
