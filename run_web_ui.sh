#!/usr/bin/env bash

SCRIPT_DIRECTORY="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$SCRIPT_DIRECTORY/.venv/bin/python" ]; then
    exec "$SCRIPT_DIRECTORY/.venv/bin/python" -m generator.webui.server "$@"
fi

exec python3 -m generator.webui.server "$@"
