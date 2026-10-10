#!/usr/bin/env bash
set -Eeuo pipefail

export PORT="${PORT:-10000}"
export AI_SERVICE_URL=http://127.0.0.1:8000
export DOCUMENT_STORAGE_PATH="${DOCUMENT_STORAGE_PATH:-/app/storage}"

mkdir -p "$DOCUMENT_STORAGE_PATH"
pnpm --dir backend db:deploy

python -m uvicorn app.main:app --app-dir /app/ai-service --host 127.0.0.1 --port 8000 &
ai_pid=$!
node backend/dist/main.js &
api_pid=$!

cleanup() {
  trap - EXIT INT TERM
  kill "$ai_pid" "$api_pid" 2>/dev/null || true
  wait "$ai_pid" "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' INT TERM

wait -n "$ai_pid" "$api_pid"
