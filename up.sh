#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=docker/config-dir.sh
source "$PROJECT_ROOT/docker/config-dir.sh"

# Raw value of KEY from config.env, with one layer of surrounding quotes removed.
read_env_value() {
    local key="$1" value
    [[ -f "$CONFIG_FILE" ]] || return 0
    value="$(awk -F= -v key="$key" '
        /^[[:space:]]*#/ { next }
        $1 == key {
            sub(/^[^=]*=/, "")
            sub(/\r$/, "")
            print
            exit
        }
    ' "$CONFIG_FILE")"
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

# Default: pull the published images. --build: build them from this checkout.
# Other arguments go to `docker compose up`.
BUILD=false
args=()
for arg in "$@"; do
    if [[ "$arg" == "--build" ]]; then
        BUILD=true
    else
        args+=("$arg")
    fi
done

if [[ ! -f "$CONFIG_FILE" ]]; then
    # A .env left in the checkout is an older setup: say where it goes rather
    # than starting over from the template.
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        die "the config now lives in $CONFIG_FILE, not in the checkout. Move it:
  mkdir -p '$PTMM_CONFIG_DIR' && mv '$PROJECT_ROOT/.env' '$CONFIG_FILE' && chmod 600 '$CONFIG_FILE'"
    fi
    created_dir=false
    [[ -d "$PTMM_CONFIG_DIR" ]] || created_dir=true
    mkdir -p "$PTMM_CONFIG_DIR"
    (umask 077 && cp "$PROJECT_ROOT/config.env.example" "$CONFIG_FILE")
    # Under sudo, hand them to the real user, who runs the backend.
    if [[ -n "${SUDO_UID:-}" ]]; then
        chown "$SUDO_UID:$SUDO_GID" "$CONFIG_FILE"
        if [[ "$created_dir" == true ]]; then
            chown "$SUDO_UID:$SUDO_GID" "$PTMM_CONFIG_DIR"
        fi
    fi
    echo "Created $CONFIG_FILE from config.env.example."
    echo "Fill it in, then run ./up.sh again."
    exit 1
fi

# It holds the TMDB key and the auth secrets.
perm="$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE")"
if (( 8#$perm & 077 )); then
    echo "Warning: $CONFIG_FILE is readable by others (mode $perm); chmod 600 it." >&2
fi

PUID="$(env_or_file PUID)"
PGID="$(env_or_file PGID)"
UMASK="$(env_or_file UMASK)"
MEDIA_DISK_MOUNT="$(env_or_file MEDIA_DISK_MOUNT)"
CERT_DIR="$(env_or_file CERT_DIR)"
CERT_FULLCHAIN_FILE="$(env_or_file CERT_FULLCHAIN_FILE)"
CERT_KEY_FILE="$(env_or_file CERT_KEY_FILE)"
TMDB_API_KEY="$(env_or_file TMDB_API_KEY)"
AUTH_ENABLED="$(env_or_file AUTH_ENABLED)"

# Under sudo, run the backend as the real user, not root.
PUID="${PUID:-${SUDO_UID:-$(id -u)}}"
PGID="${PGID:-${SUDO_GID:-$(id -g)}}"
UMASK="${UMASK:-002}"
CERT_FULLCHAIN_FILE="${CERT_FULLCHAIN_FILE:-fullchain.pem}"
CERT_KEY_FILE="${CERT_KEY_FILE:-privkey.pem}"

for key in PUID PGID; do
    [[ "${!key}" =~ ^[0-9]+$ ]] || die "$key must be numeric: ${!key}"
done
[[ "$UMASK" =~ ^[0-7]{3,4}$ ]] || die "UMASK must be an octal value such as 002 or 0022"

# Both services run on the host's network, so these are host ports.
HTTPS_PORT="$(env_or_file HTTPS_PORT)"
BACKEND_PORT="$(env_or_file BACKEND_PORT)"
HTTPS_PORT="${HTTPS_PORT:-8443}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
for key in HTTPS_PORT BACKEND_PORT; do
    [[ "${!key}" =~ ^[0-9]+$ ]] && (( ${!key} >= 1 && ${!key} <= 65535 )) \
        || die "$key must be a port number: ${!key}"
done
[[ "$HTTPS_PORT" != "$BACKEND_PORT" ]] || die "HTTPS_PORT and BACKEND_PORT must differ"

for key in TMDB_API_KEY MEDIA_DISK_MOUNT CERT_DIR; do
    [[ -n "${!key}" ]] || die "$key must be set in $CONFIG_FILE"
done
[[ "$TMDB_API_KEY" != replace-with-* ]] || die "TMDB_API_KEY is still the placeholder from config.env.example"

[[ -d "$MEDIA_DISK_MOUNT" ]] || die "MEDIA_DISK_MOUNT is not a directory: $MEDIA_DISK_MOUNT"
# Cert dirs are often root-only (e.g. /etc/nginx/certs), which is fine: Docker
# mounts them as root and nginx's master process reads them as root. Check as
# the invoking user first, then via sudo (silently if it needs no password,
# otherwise prompting once).
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
    # Compose expands $ inside unquoted/double-quoted values, which silently
    # mangles a bcrypt hash ($2b$12$...).
    raw_hash="$(awk -F= '$1 == "AUTH_PASSWORD_HASH" { sub(/^[^=]*=/, ""); print; exit }' "$CONFIG_FILE")"
    if [[ -n "$raw_hash" && "$raw_hash" == *'$'* && ! "$raw_hash" =~ ^\'.*\'$ ]]; then
        die "AUTH_PASSWORD_HASH in $CONFIG_FILE must be wrapped in single quotes: AUTH_PASSWORD_HASH='\$2b\$12\$...'"
    fi
fi

# The backend keeps ptmm.db and bak/ here too.
[[ -w "$PTMM_CONFIG_DIR" ]] || die "config directory is not writable: $PTMM_CONFIG_DIR"
if [[ -e "$PTMM_CONFIG_DIR/ptmm.db" ]]; then
    owner="$(stat -c '%u' "$PTMM_CONFIG_DIR/ptmm.db" 2>/dev/null || stat -f '%u' "$PTMM_CONFIG_DIR/ptmm.db")"
    [[ "$owner" == "$PUID" ]] || die "$PTMM_CONFIG_DIR/ptmm.db is owned by uid $owner, expected $PUID (chown it, or set PUID)"
fi

export PUID PGID UMASK CERT_FULLCHAIN_FILE CERT_KEY_FILE HTTPS_PORT BACKEND_PORT

echo "Starting PT Media Manager"
echo "  Config dir       $PTMM_CONFIG_DIR"
echo "  Backend UID:GID  $PUID:$PGID"
echo "  Media disk       $MEDIA_DISK_MOUNT"
echo "  Certificates     $CERT_DIR ($CERT_FULLCHAIN_FILE, $CERT_KEY_FILE)"
echo "  Ports            HTTPS $HTTPS_PORT, backend 127.0.0.1:$BACKEND_PORT"

# --env-file on every call: without it Compose reads only a .env in the checkout.
compose() {
    docker compose --env-file "$CONFIG_FILE" "$@"
}

cd "$PROJECT_ROOT"
compose config --quiet
if [[ "$BUILD" == true ]]; then
    compose up -d --build ${args[@]+"${args[@]}"}
else
    compose pull
    compose up -d ${args[@]+"${args[@]}"}
fi
# Drop the image layers the update left untagged.
docker image prune -f
