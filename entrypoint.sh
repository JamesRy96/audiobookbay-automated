#!/bin/sh
# File: entrypoint.sh
set -e

# Resolve startup setting names once. Read literal assignments; never evaluate shell code from values.
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
settings_file="$(mktemp)"
trap 'rm -f "$settings_file"' EXIT
python3 "$SCRIPT_DIR/audiobook_automated/environment.py" > "$settings_file"
while IFS= read -r setting; do
    case "$setting" in
        *=*) export "${setting?}" ;;
        *) unset "$setting" ;;
    esac
done < "$settings_file"
rm -f "$settings_file"
trap - EXIT

# Intelligent Bind Logic for Gunicorn
if [ -z "${LISTEN_HOST:-}" ]; then
    if python3 -c "import socket; s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM); s.bind(('::', 0)); s.close()" 2>/dev/null; then
        export LISTEN_HOST="[::]"
        echo "Auto-detected IPv6 support. Binding Gunicorn to [::]"
    else
        export LISTEN_HOST="0.0.0.0"
        echo "IPv6 not available. Binding Gunicorn to 0.0.0.0"
    fi
else
    echo "Using user-defined LISTEN_HOST: $LISTEN_HOST"
fi

# Use default port 5078 if LISTEN_PORT env var is not set
export LISTEN_PORT="${LISTEN_PORT:-5078}"

# CONCURRENCY SETTINGS
export THREADS="${THREADS:-8}"
export TIMEOUT="${TIMEOUT:-60}"
export PYTHONOPTIMIZE=1

# LOGGING
LOG_LEVEL_VAL="$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
export LOG_LEVEL="$LOG_LEVEL_VAL"
export FLASK_DEBUG="${FLASK_DEBUG:-0}"

# --- Permission Fix (LinuxServer.io style) ---
# Retrieve requested PUID/PGID (default to standard 1000:1000)
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Setting permissions: UID=$PUID, GID=$PGID"

# Modify the 'appuser' created in Dockerfile to match the requested IDs
# usermod/groupmod allow the container to read/write volumes mounted by the host user
groupmod -o -g "$PGID" appuser
usermod -o -u "$PUID" appuser

echo "Starting Gunicorn with 1 worker and $THREADS threads at log level $LOG_LEVEL."

# Drop root privileges and execute Gunicorn as appuser
# 'exec' ensures Gunicorn becomes PID 1 (or child of) to handle signals correctly
exec gosu appuser gunicorn --preload \
    --log-level "$LOG_LEVEL" \
    --access-logfile - \
    --error-logfile - \
    --bind "${LISTEN_HOST}:${LISTEN_PORT}" \
    --forwarded-allow-ips "" \
    --workers 1 \
    --threads "$THREADS" \
    --timeout "$TIMEOUT" \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    audiobook_automated.app:app
