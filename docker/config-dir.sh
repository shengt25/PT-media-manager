# Sourced by up.sh, compose.sh and gen-auth.sh: where the config lives.
#
# PTMM_CONFIG_DIR holds config.env, the database and its backups. It can only
# come from the environment, never from config.env, since it says where
# config.env is. Default: ~/.config/ptmm of the invoking user (the real user
# under sudo).

INVOKING_HOME="$HOME"
if [[ -n "${SUDO_USER:-}" ]]; then
    INVOKING_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
fi

PTMM_CONFIG_DIR="${PTMM_CONFIG_DIR:-$INVOKING_HOME/.config/ptmm}"
if [[ "$PTMM_CONFIG_DIR" != /* ]]; then
    echo "Error: PTMM_CONFIG_DIR must be an absolute path: $PTMM_CONFIG_DIR" >&2
    exit 1
fi
PTMM_CONFIG_DIR="${PTMM_CONFIG_DIR%/}"
CONFIG_FILE="$PTMM_CONFIG_DIR/config.env"
export PTMM_CONFIG_DIR
