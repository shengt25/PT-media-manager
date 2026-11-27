#!/usr/bin/env bash
# `docker compose` with this project's config.env, for everyday commands:
#   ./compose.sh logs -f
#   ./compose.sh ps
#   ./compose.sh down
# Start and update with ./up.sh: it validates the config and fills in the
# defaults (backend user, ports) that `up` needs.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=docker/config-dir.sh
source "$PROJECT_ROOT/docker/config-dir.sh"

case "${1:-}" in
    up|create|run)
        echo "Error: use ./up.sh to start or update PT Media Manager." >&2
        exit 1
        ;;
esac
[[ -f "$CONFIG_FILE" ]] || { echo "Error: $CONFIG_FILE not found; run ./up.sh first." >&2; exit 1; }

cd "$PROJECT_ROOT"
exec docker compose --env-file "$CONFIG_FILE" "$@"
