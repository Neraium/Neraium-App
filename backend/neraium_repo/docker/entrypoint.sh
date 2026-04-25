#!/usr/bin/env sh
set -eu

# If a command is explicitly provided (e.g. `python -m ui.app`), run it directly.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Production packaging default. Can be overridden explicitly by env.
export NERAIUM_RUNTIME_MODE="${NERAIUM_RUNTIME_MODE:-production}"

# Ensure writable parent exists for local persistence.
db_path="${NERAIUM_DB_PATH:-/data/neraium.db}"
db_dir="$(dirname "$db_path")"
mkdir -p "$db_dir"

# Optional integration config path can point to mounted read-only config.
# If unset, app still starts and pull mapping falls back to defaults.

if ! python -c "import importlib; importlib.import_module(\"apps.api.main\")" >/dev/null 2>&1; then
  if [ -f "main.py" ]; then
    export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}../.."
  fi
fi

python -c "import importlib; importlib.import_module(\"apps.api.main\")" >/dev/null 2>&1 || {
  echo "Unable to import apps.api.main from cwd=$(pwd)" >&2
  exit 1
}

exec python -m uvicorn apps.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --h11-max-incomplete-event-size "${NERAIUM_UVICORN_H11_MAX_INCOMPLETE_EVENT_SIZE:-67108864}"
