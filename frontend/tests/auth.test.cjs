const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(file, imports = {}) {
  const source = fs.readFileSync(path.resolve(__dirname, '..', file), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(name => imports[name] || require(name), module, module.exports);
  return module.exports;
}
const auth = load('lib/auth.ts');
const { api, ApiError } = load('lib/api.ts', { '@/lib/auth': auth });

test('accepts only the exact company email domain, ignoring case and surrounding spaces', () => {
  assert.equal(auth.isCompanyEmail(' Member@UNIGROUP.COM.VN '), true);
  for (const email of ['member@gmail.com', 'member@sub.unigroup.com.vn', 'member@unigroup.com.vn.evil.com', 'member@evilunigroup.com.vn', 'member@@unigroup.com.vn', '@unigroup.com.vn']) {
    assert.equal(auth.isCompanyEmail(email), false, email);
  }
});

test('restores saved-result links and keeps login redirects inside permitted application pages', () => {
  assert.equal(auth.loginDestination('/?search=saved', 'USER'), '/?search=saved');
  assert.equal(auth.loginDestination('/history', 'USER'), '/history');
  assert.equal(auth.loginDestination('/admin', 'ADMIN'), '/admin');
  for (const next of [null, 'https://evil.example', '//evil.example', '/\\evil.example', '/auth', '/admin', '/unknown']) {
    assert.equal(auth.loginDestination(next, 'USER'), '/', String(next));
  }
});

test('withholds protected page content until the session is checked and leaves the login page accessible', () => {
  let pathname = '/';
  const { AuthProvider } = load('components/auth-provider.tsx', {
    'next/navigation': { usePathname: () => pathname, useRouter: () => ({ replace() {} }) },
    'next/link': { default: ({ children }) => React.createElement('a', null, children) },
    '@/lib/api': { api, ApiError },
    '@/lib/auth': auth,
    '@/components/ui/button': { Button: ({ children }) => React.createElement('button', null, children) },
  });
  for (pathname of ['/', '/history', '/admin']) {
    const html = renderToStaticMarkup(React.createElement(AuthProvider, null, 'protected-content'));
    assert.doesNotMatch(html, /protected-content/);
    assert.match(html, /Đang kiểm tra đăng nhập/);
  }
  pathname = '/auth';
  assert.match(renderToStaticMarkup(React.createElement(AuthProvider, null, 'login-form')), /login-form/);
});

test('sends credentials, expires rejected sessions, and keeps valid sessions on role errors', async t => {
  const originals = { fetch: global.fetch, window: global.window, sessionStorage: global.sessionStorage };
  t.after(() => { Object.assign(global, originals); });
  global.window = new EventTarget();
  const values = new Map();
  global.sessionStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  let expired = 0;
  window.addEventListener(auth.AUTH_EXPIRED_EVENT, () => expired++);

  values.set(auth.AUTH_TOKEN_KEY, 'valid-token');
  global.fetch = async (_url, options) => {
    assert.equal(options.headers.authorization, 'Bearer valid-token');
    return new Response(JSON.stringify({ ok: true }));
  };
  assert.deepEqual(await api('/hs-codes/search?q=6109'), { ok: true });

  global.fetch = async () => new Response(JSON.stringify({ message: 'Forbidden' }), { status: 403 });
  await assert.rejects(api('/admin/documents'), error => error instanceof ApiError && error.status === 403);
  assert.equal(values.get(auth.AUTH_TOKEN_KEY), 'valid-token');
  assert.equal(expired, 0);

  for (const [status, body] of [[401, { message: 'Expired' }], [403, { code: 'EMAIL_DOMAIN_NOT_ALLOWED' }]]) {
    values.set(auth.AUTH_TOKEN_KEY, 'valid-token');
    global.fetch = async () => new Response(JSON.stringify(body), { status });
    await assert.rejects(api('/classification/history'));
    assert.equal(values.has(auth.AUTH_TOKEN_KEY), false);
  }
  assert.equal(expired, 2);

  values.set(auth.AUTH_TOKEN_KEY, 'valid-token');
  global.fetch = async (_url, options) => {
    assert.equal(options.headers.authorization, undefined);
    return new Response(JSON.stringify({ message: 'Wrong password' }), { status: 401 });
  };
  await assert.rejects(api('/auth/login', { method: 'POST' }));
  assert.equal(values.get(auth.AUTH_TOKEN_KEY), 'valid-token');
  assert.equal(expired, 2);
});
