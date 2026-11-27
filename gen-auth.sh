#!/usr/bin/env bash
# Prints AUTH_PASSWORD_HASH / JWT_SECRET lines to paste into .env, computed
# inside the backend image so the host needs nothing but Docker.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

read -rsp "Password for the PT Media Manager login: " password
echo ""
[[ -n "$password" ]] || { echo "Error: password cannot be empty." >&2; exit 1; }

docker build -q -f "$PROJECT_ROOT/docker/backend.Dockerfile" -t ptmm-backend "$PROJECT_ROOT" >/dev/null

# Password goes in over stdin, never on a command line.
printf '%s' "$password" | docker run --rm -i ptmm-backend python -c '
import bcrypt, secrets, sys
password = sys.stdin.buffer.read()
print("AUTH_PASSWORD_HASH=\x27" + bcrypt.hashpw(password, bcrypt.gensalt()).decode() + "\x27")
print("JWT_SECRET=" + secrets.token_hex(32))
'
