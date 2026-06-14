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

echo "Uninstalling PT Media Manager..."
read -r -p "This will stop services and remove system configs. Continue? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

#  Read install state 

MODE="public"  # safe default: try to remove everything
if [[ -f "$STATE_FILE" ]]; then
    load_state
else
    echo "Warning: .ptmm-install not found, assuming public mode."
fi

#  Remove systemd service (public mode only) 

if [[ "$MODE" == "public" ]]; then
    if systemctl is-active --quiet ptmm 2>/dev/null; then
        sudo systemctl stop ptmm
    fi
    sudo systemctl disable ptmm 2>/dev/null || true
    sudo rm -f /etc/systemd/system/ptmm.service
    sudo systemctl daemon-reload
    echo "Systemd service removed."

    #  Remove nginx config 

    sudo rm -f /etc/nginx/sites-enabled/ptmm
    sudo rm -f /etc/nginx/sites-available/ptmm
    if sudo nginx -t 2>/dev/null; then
        sudo systemctl reload nginx
    fi
    echo "Nginx config removed."

    FRONTEND_ROOT="${FRONTEND_ROOT:-}"
    if [[ -n "$FRONTEND_ROOT" ]]; then
        echo ""
        read -r -p "Remove deployed frontend files at $FRONTEND_ROOT? [y/N] " remove_frontend
        if [[ "$remove_frontend" == "y" || "$remove_frontend" == "Y" ]]; then
            if [[ "$FRONTEND_ROOT" == "/" ]]; then
                echo "Refusing to remove /."
            else
                sudo rm -rf "$FRONTEND_ROOT"
                echo "Frontend files removed."
            fi
        else
            echo "Frontend files kept at $FRONTEND_ROOT."
        fi
    fi
fi

#  Remove state file 

rm -f "$STATE_FILE"

echo ""
echo "Done. Project files at $PROJECT_ROOT are untouched."
echo "Remove them manually if needed: rm -rf $PROJECT_ROOT"
