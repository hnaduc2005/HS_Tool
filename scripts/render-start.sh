#!/usr/bin/env bash
set -Eeuo pipefail

export PORT="${PORT:-10000}"
export AI_SERVICE_URL=http://127.0.0.1:8000
export DOCUMENT_STORAGE_PATH="${DOCUMENT_STORAGE_PATH:-/app/storage}"

printf 'Starting commit %s on public port %s\n' "${RENDER_GIT_COMMIT:-unknown}" "$PORT"
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
trap 'echo "Shutdown requested; stopping services"; exit 0' INT TERM

set +e
wait -n "$ai_pid" "$api_pid"
service_status=$?
set -e
if kill -0 "$ai_pid" 2>/dev/null; then
  echo "NestJS exited unexpectedly (status $service_status)" >&2
else
  echo "FastAPI exited unexpectedly (status $service_status)" >&2
fi
if [ "$service_status" -eq 0 ]; then
  exit 1
fi
exit "$service_status"
