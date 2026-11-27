#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# Raw value of KEY from .env, with one layer of surrounding quotes removed.
read_env_value() {
    local key="$1" value
    [[ -f "$ENV_FILE" ]] || return 0
    value="$(awk -F= -v key="$key" '
        /^[[:space:]]*#/ { next }
        $1 == key {
            sub(/^[^=]*=/, "")
            sub(/\r$/, "")
            print
            exit
        }
    ' "$ENV_FILE")"
    if [[ "$value" =~ ^\'(.*)\'$ || "$value" =~ ^\"(.*)\"$ ]]; then
        value="${BASH_REMATCH[1]}"
    fi
    printf '%s' "$value"
}

env_or_file() {
    local key="$1"
    local current="${!key:-}"
    if [[ -n "$current" ]]; then
        printf '%s' "$current"
    else
        read_env_value "$key"
    fi
}

die() {
    echo "Error: $*" >&2
    exit 1
}

[[ -f "$ENV_FILE" ]] || die ".env not found — copy .env.example to .env and edit it"

PUID="$(env_or_file PUID)"
PGID="$(env_or_file PGID)"
UMASK="$(env_or_file UMASK)"
DATA_DIR="$(env_or_file DATA_DIR)"
MEDIA_DISK_MOUNT="$(env_or_file MEDIA_DISK_MOUNT)"
CERT_DIR="$(env_or_file CERT_DIR)"
CERT_FULLCHAIN_FILE="$(env_or_file CERT_FULLCHAIN_FILE)"
CERT_KEY_FILE="$(env_or_file CERT_KEY_FILE)"
TMDB_API_KEY="$(env_or_file TMDB_API_KEY)"
AUTH_ENABLED="$(env_or_file AUTH_ENABLED)"

# Under sudo, run the containers as (and keep data with) the real user, not root.
INVOKING_HOME="$HOME"
if [[ -n "${SUDO_USER:-}" ]]; then
    INVOKING_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
fi

PUID="${PUID:-${SUDO_UID:-$(id -u)}}"
PGID="${PGID:-${SUDO_GID:-$(id -g)}}"
UMASK="${UMASK:-002}"
DATA_DIR="${DATA_DIR:-$INVOKING_HOME/.config/ptmm}"
CERT_FULLCHAIN_FILE="${CERT_FULLCHAIN_FILE:-fullchain.pem}"
CERT_KEY_FILE="${CERT_KEY_FILE:-privkey.pem}"

for key in PUID PGID; do
    [[ "${!key}" =~ ^[0-9]+$ ]] || die "$key must be numeric: ${!key}"
done
[[ "$UMASK" =~ ^[0-7]{3,4}$ ]] || die "UMASK must be an octal value such as 002 or 0022"

for key in TMDB_API_KEY MEDIA_DISK_MOUNT CERT_DIR; do
    [[ -n "${!key}" ]] || die "$key must be set in .env or the environment"
done
[[ "$TMDB_API_KEY" != replace-with-* ]] || die "TMDB_API_KEY is still the placeholder from .env.example"

[[ -d "$MEDIA_DISK_MOUNT" ]] || die "MEDIA_DISK_MOUNT is not a directory: $MEDIA_DISK_MOUNT"
# Cert dirs are often root-only (e.g. /etc/nginx/certs), which is fine: Docker
# mounts them as root and nginx's master process reads them as root. So only
# check what we can see — directly, or via sudo if it needs no password.
cert_test() {
    test "$@" 2>/dev/null || sudo -n test "$@" 2>/dev/null
}
if cert_test -d "$CERT_DIR"; then
    for f in "$CERT_FULLCHAIN_FILE" "$CERT_KEY_FILE"; do
        cert_test -e "$CERT_DIR/$f" || die "certificate file not found: $CERT_DIR/$f"
    done
elif sudo test -d "$CERT_DIR" 2>/dev/null; then
    # Password-protected sudo: ask once rather than failing the check.
    for f in "$CERT_FULLCHAIN_FILE" "$CERT_KEY_FILE"; do
        sudo test -e "$CERT_DIR/$f" || die "certificate file not found: $CERT_DIR/$f"
    done
else
    die "CERT_DIR not found (checked as $(whoami) and with sudo): $CERT_DIR"
fi

if [[ "$AUTH_ENABLED" == "true" ]]; then
    for key in AUTH_USERNAME AUTH_PASSWORD_HASH JWT_SECRET; do
        [[ -n "$(env_or_file "$key")" ]] || die "AUTH_ENABLED=true requires $key (generate with ./gen-auth.sh)"
    done
    # Compose expands $ inside unquoted/double-quoted .env values, which
    # silently mangles a bcrypt hash ($2b$12$...).
    raw_hash="$(awk -F= '$1 == "AUTH_PASSWORD_HASH" { sub(/^[^=]*=/, ""); print; exit }' "$ENV_FILE")"
    if [[ -n "$raw_hash" && "$raw_hash" == *'$'* && ! "$raw_hash" =~ ^\'.*\'$ ]]; then
        die "AUTH_PASSWORD_HASH in .env must be wrapped in single quotes: AUTH_PASSWORD_HASH='\$2b\$12\$...'"
    fi
fi

mkdir -p "$DATA_DIR"
[[ -w "$DATA_DIR" ]] || die "database directory is not writable: $DATA_DIR"
if [[ -e "$DATA_DIR/ptmm.db" ]]; then
    owner="$(stat -c '%u' "$DATA_DIR/ptmm.db" 2>/dev/null || stat -f '%u' "$DATA_DIR/ptmm.db")"
    [[ "$owner" == "$PUID" ]] || die "$DATA_DIR/ptmm.db is owned by uid $owner, expected $PUID (chown it, or set PUID)"
fi

export PUID PGID UMASK DATA_DIR CERT_FULLCHAIN_FILE CERT_KEY_FILE

echo "Starting PT Media Manager"
echo "  Backend UID:GID  $PUID:$PGID"
echo "  Media disk       $MEDIA_DISK_MOUNT"
echo "  Database dir     $DATA_DIR"
echo "  Certificates     $CERT_DIR ($CERT_FULLCHAIN_FILE, $CERT_KEY_FILE)"

cd "$PROJECT_ROOT"
docker compose config --quiet
docker compose up -d --build "$@"
