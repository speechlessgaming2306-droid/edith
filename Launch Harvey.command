#!/bin/zsh

set -e

cd "$(dirname "$0")"

mkdir -p .cache/matplotlib .cache/fontconfig

export PATH="$PWD/.venv/bin:$PATH"
export PYTHON_BIN="$PWD/.venv/bin/python3"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export NODE_ENV="production"
unset ELECTRON_RUN_AS_NODE

existing_listener="$(lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$existing_listener" ]]; then
  stale_pids=()
  while IFS= read -r line; do
    pid="$(echo "$line" | awk 'NR>1 {print $2}')"
    [[ -z "$pid" ]] && continue
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$cmd" == *"backend/server.py"* || "$cmd" == *"uvicorn"* || "$cmd" == *"harv/.venv/bin/python"* ]]; then
      stale_pids+=("$pid")
    fi
  done <<< "$existing_listener"

  if (( ${#stale_pids[@]} > 0 )); then
    echo "Clearing stale Edith backend on port 8000..."
    kill "${stale_pids[@]}" 2>/dev/null || true
    sleep 1
  fi
fi

npm run build
npm start
