#!/usr/bin/env bash
set -Eeuo pipefail

app_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$app_dir"

export PORT="${PORT:-10000}"
export AI_SERVICE_URL=http://127.0.0.1:8000
export DOCUMENT_STORAGE_PATH="${DOCUMENT_STORAGE_PATH:-/app/storage}"
export PYTHONUNBUFFERED=1

migration_timeout="${MIGRATION_TIMEOUT_SECONDS:-180}"
if [[ ! "$migration_timeout" =~ ^[1-9][0-9]{0,2}$ ]] || [ "$migration_timeout" -gt 900 ]; then
  echo "MIGRATION_TIMEOUT_SECONDS must be an integer from 1 to 900" >&2
  exit 1
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required for migrations and API startup" >&2
  exit 1
fi
for required_file in backend/node_modules/prisma/build/index.js backend/prisma/schema.prisma backend/dist/main.js; do
  if [ ! -f "$required_file" ]; then
    printf 'Missing build artifact: %s; rebuild the Docker image\n' "$required_file" >&2
    exit 1
  fi
done

ai_pid=""
api_pid=""
migration_pid=""
cleanup() {
  trap - EXIT INT TERM
  local pid
  for pid in "$migration_pid" "$ai_pid" "$api_pid"; do
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi
  done
  for pid in "$migration_pid" "$ai_pid" "$api_pid"; do
    if [ -n "$pid" ]; then wait "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT
trap 'echo "Shutdown requested; stopping services"; exit 0' INT TERM

printf 'Starting commit %s on public port %s\n' "${RENDER_GIT_COMMIT:-unknown}" "$PORT"
mkdir -p "$DOCUMENT_STORAGE_PATH"
printf 'Running Prisma migrations (timeout: %ss)\n' "$migration_timeout"
# pnpm 11 can auto-install before running a script. Runtime must use the
# dependencies already installed and verified during the Docker build.
timeout --kill-after=10s "${migration_timeout}s" \
  node backend/node_modules/prisma/build/index.js migrate deploy --schema backend/prisma/schema.prisma &
migration_pid=$!
if wait "$migration_pid"; then
  migration_pid=""
  echo "Prisma migrations completed"
else
  migration_status=$?
  migration_pid=""
  if [ "$migration_status" -eq 124 ] || [ "$migration_status" -eq 137 ]; then
    printf 'Prisma migrations timed out after %ss; check database connectivity and migration locks\n' "$migration_timeout" >&2
  else
    printf 'Prisma migrations failed (status %s); services were not started\n' "$migration_status" >&2
  fi
  exit "$migration_status"
fi

echo "Starting FastAPI on 127.0.0.1:8000"
python -m uvicorn app.main:app --app-dir "$app_dir/ai-service" --host 127.0.0.1 --port 8000 &
ai_pid=$!
printf 'Starting NestJS on 0.0.0.0:%s\n' "$PORT"
node backend/dist/main.js &
api_pid=$!

set +e
exited_pid=""
wait -n -p exited_pid "$ai_pid" "$api_pid"
service_status=$?
set -e
if [ "${exited_pid:-}" = "$api_pid" ]; then
  echo "NestJS exited unexpectedly (status $service_status)" >&2
elif [ "${exited_pid:-}" = "$ai_pid" ]; then
  echo "FastAPI exited unexpectedly (status $service_status)" >&2
else
  echo "Service supervisor ended unexpectedly (status $service_status)" >&2
fi
if [ "$service_status" -eq 0 ]; then
  exit 1
fi
exit "$service_status"
