import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { delimiter, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

// Exercise the supervisor with local process doubles; never connect to a DB/AI.
const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const fixtureRoot = join(repo, '.logs', 'render-start-tests');
const bash = process.env.BASH_TEST_BINARY || 'bash';
mkdirSync(fixtureRoot, { recursive: true });

const nodeDouble = `#!/usr/bin/env bash
set -eu
printf 'node %s\\n' "$*" >> "$TEST_EVENTS"
if [[ "$1" == */prisma/build/index.js ]]; then
  echo migration-started >> "$TEST_EVENTS"
  case "$MIGRATION_MODE" in
    fail) exit 42 ;;
    hang) exec sleep 30 ;;
  esac
  exit 0
fi
echo "api-started port=$PORT" >> "$TEST_EVENTS"
trap 'echo api-stopped >> "$TEST_EVENTS"; exit 0' TERM INT
if [ "$API_MODE" = fail ]; then sleep 0.15; exit 17; fi
if [ "$API_MODE" = clean-exit ]; then sleep 0.15; exit 0; fi
while :; do sleep 0.05; done
`;
const pythonDouble = `#!/usr/bin/env bash
set -eu
echo "ai-started args=$* url=$AI_SERVICE_URL unbuffered=$PYTHONUNBUFFERED" >> "$TEST_EVENTS"
trap 'echo ai-stopped >> "$TEST_EVENTS"; exit 0' TERM INT
if [ "$AI_MODE" = fail ]; then sleep 0.15; exit 23; fi
while :; do sleep 0.05; done
`;
const pnpmDouble = `#!/usr/bin/env bash
echo unexpected-pnpm-runtime-install >> "$TEST_EVENTS"
exit 88
`;
const shutdownRunner = `#!/usr/bin/env bash
set -eu
bash scripts/render-start.sh &
startup_pid=$!
for ((attempt=0; attempt<200; attempt++)); do
  if [ -f "$TEST_EVENTS" ]; then
    events=$(< "$TEST_EVENTS")
    if [[ "$events" == *"$STOP_STAGE"* ]]; then
      kill -TERM "$startup_pid"
      wait "$startup_pid"
      exit $?
    fi
  fi
  sleep 0.05
done
kill -TERM "$startup_pid" 2>/dev/null || true
wait "$startup_pid" || true
echo "Fixture did not reach shutdown stage" >&2
exit 99
`;

async function runFixture(overrides = {}, options = {}) {
  const dir = mkdtempSync(join(fixtureRoot, 'case-'));
  const eventsPath = join(dir, 'events.txt');
  try {
    for (const path of ['scripts', 'bin', 'backend/node_modules/prisma/build', 'backend/prisma', 'backend/dist', 'ai-service']) {
      mkdirSync(join(dir, path), { recursive: true });
    }
    copyFileSync(join(repo, 'scripts/render-start.sh'), join(dir, 'scripts/render-start.sh'));
    for (const path of ['backend/node_modules/prisma/build/index.js', 'backend/prisma/schema.prisma', 'backend/dist/main.js']) {
      writeFileSync(join(dir, path), '// fixture, never executed by real Node\n');
    }
    for (const [name, body] of [['node', nodeDouble], ['python', pythonDouble], ['pnpm', pnpmDouble]]) {
      writeFileSync(join(dir, 'bin', name), body, { mode: 0o755 });
    }
    writeFileSync(join(dir, 'shutdown.sh'), shutdownRunner, { mode: 0o755 });
    if (options.missingArtifact) rmSync(join(dir, options.missingArtifact));
    const env = { ...process.env };
    const inheritedPath = env.PATH || env.Path || '';
    for (const key of Object.keys(env)) if (key.toLowerCase() === 'path') delete env[key];
    Object.assign(env, {
      PATH: `${join(dir, 'bin')}${delimiter}${inheritedPath}`,
      TEST_EVENTS: eventsPath.replaceAll('\\', '/'),
      DATABASE_URL: 'postgresql://fixture:fixture@127.0.0.1:1/fixture',
      DOCUMENT_STORAGE_PATH: join(dir, 'storage').replaceAll('\\', '/'),
      RENDER_GIT_COMMIT: 'fixture-commit', PORT: '10000',
      AI_SERVICE_URL: 'https://unused.invalid',
      MIGRATION_TIMEOUT_SECONDS: '1',
      MIGRATION_MODE: 'success', API_MODE: 'running', AI_MODE: 'running',
      ...overrides,
    });
    const child = spawn(bash, [options.shutdown ? 'shutdown.sh' : 'scripts/render-start.sh'], { cwd: dir, env });
    let output = '';
    child.stdout.on('data', (chunk) => { output += chunk; });
    child.stderr.on('data', (chunk) => { output += chunk; });
    const exit = await new Promise((resolveExit, reject) => {
      const deadline = setTimeout(() => {
        child.kill();
        reject(new Error(`Startup fixture exceeded 15 seconds:\n${output}`));
      }, 15000);
      child.once('error', (error) => { clearTimeout(deadline); reject(error); });
      child.once('close', (code) => { clearTimeout(deadline); resolveExit(code); });
    });
    const events = existsSync(eventsPath) ? readFileSync(eventsPath, 'utf8') : '';
    assert.doesNotMatch(events, /unexpected-pnpm-runtime-install/);
    return { exit, output, events };
  } finally {
    const within = relative(fixtureRoot, resolve(dir));
    assert.ok(within.startsWith('case-') && !within.includes('..'), 'Cleanup must stay inside fixture root');
    rmSync(dir, { recursive: true, force: true });
  }
}

test('migration failure exits with its status before either service starts', async () => {
  const result = await runFixture({ MIGRATION_MODE: 'fail' });
  assert.equal(result.exit, 42);
  assert.match(result.output, /Prisma migrations failed \(status 42\)/);
  assert.doesNotMatch(result.events, /api-started|ai-started/);
});

test('stalled migration times out instead of waiting for Render port scan', async () => {
  const result = await runFixture({ MIGRATION_MODE: 'hang' });
  assert.equal(result.exit, 124);
  assert.match(result.output, /Prisma migrations timed out after 1s/);
  assert.doesNotMatch(result.events, /api-started|ai-started/);
});

test('API failure stops the AI service and preserves the failure status', async () => {
  const result = await runFixture({ API_MODE: 'fail' });
  assert.equal(result.exit, 17);
  assert.match(result.output, /NestJS exited unexpectedly \(status 17\)/);
  assert.match(result.events, /ai-stopped/);
  assert.match(result.events, /api-started port=10000/);
  assert.match(result.events, /url=http:\/\/127\.0\.0\.1:8000 unbuffered=1/);
  assert.match(result.events, /migrate deploy --schema backend\/prisma\/schema\.prisma/);
});

test('AI failure stops the API and preserves the failure status', async () => {
  const result = await runFixture({ AI_MODE: 'fail' });
  assert.equal(result.exit, 23);
  assert.match(result.output, /FastAPI exited unexpectedly \(status 23\)/);
  assert.match(result.events, /api-stopped/);
});

test('unexpected clean service exit is still a failed container', async () => {
  const result = await runFixture({ API_MODE: 'clean-exit' });
  assert.equal(result.exit, 1);
  assert.match(result.output, /NestJS exited unexpectedly \(status 0\)/);
  assert.match(result.events, /ai-stopped/);
});

test('TERM shuts down both running services cleanly', async () => {
  const result = await runFixture({ STOP_STAGE: 'api-started' }, { shutdown: true });
  assert.equal(result.exit, 0);
  assert.match(result.output, /Shutdown requested; stopping services/);
  assert.match(result.events, /ai-stopped/);
  assert.match(result.events, /api-stopped/);
});

test('TERM during migration stops startup before launching services', async () => {
  const result = await runFixture({ MIGRATION_MODE: 'hang', STOP_STAGE: 'migration-started' }, { shutdown: true });
  assert.equal(result.exit, 0);
  assert.match(result.output, /Shutdown requested; stopping services/);
  assert.doesNotMatch(result.events, /api-started|ai-started/);
});

test('missing DATABASE_URL fails before migrations', async () => {
  const result = await runFixture({ DATABASE_URL: '' });
  assert.equal(result.exit, 1);
  assert.match(result.output, /DATABASE_URL is required/);
  assert.equal(result.events, '');
});

test('missing build artifact reports what must be rebuilt', async () => {
  const result = await runFixture({}, { missingArtifact: 'backend/dist/main.js' });
  assert.equal(result.exit, 1);
  assert.match(result.output, /Missing build artifact: backend\/dist\/main.js/);
  assert.equal(result.events, '');
});

test('invalid migration timeout cannot become an unbounded wait', async () => {
  const result = await runFixture({ MIGRATION_TIMEOUT_SECONDS: '0' });
  assert.equal(result.exit, 1);
  assert.match(result.output, /MIGRATION_TIMEOUT_SECONDS must be an integer/);
});
