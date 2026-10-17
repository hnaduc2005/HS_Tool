import { Test } from '@nestjs/testing';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './module';
import { Database } from './database';
import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';

describe('HTTP API', () => {
  let app: any; let base: string;
  let passwordHash: string;
  const member = { id: 'user-1', email: 'member@unigroup.com.vn', role: 'USER' };
  const external = { id: 'external-1', email: 'old@example.com', role: 'ADMIN' };
  const admin = { id: 'admin-1', email: 'admin@unigroup.com.vn', role: 'ADMIN' };
  const headers = (id = member.id, role = 'USER') => ({ authorization: `Bearer ${jwt.sign({ sub: id, role }, process.env.JWT_SECRET!)}`, 'content-type': 'application/json' });
  beforeAll(async () => {
    process.env.JWT_SECRET = 'a-very-long-test-secret-at-least-32-characters';
    passwordHash = await bcrypt.hash('correct-password', 4);
    const db = {
      $queryRaw: jest.fn().mockResolvedValue([{ ok: 1 }]),
      hsCode: { findMany: jest.fn().mockResolvedValue([{ code: '61091010', description: 'Áo phông nam' }]) },
      document: { findMany: jest.fn().mockResolvedValue([]) },
      user: { findUnique: jest.fn().mockImplementation(({ where }) => {
        const user = [member, external, admin].find(user => where.id ? user.id === where.id : user.email === where.email);
        return Promise.resolve(user ? { ...user, passwordHash } : null);
      }) },
      classificationSearch: { findUnique: jest.fn().mockResolvedValue({ id: 'saved', userId: 'other-user', results: [] }) },
    };
    const module = await Test.createTestingModule({ imports: [AppModule] }).overrideProvider(Database).useValue(db).compile();
    app = module.createNestApplication();
    app.setGlobalPrefix('api');
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
    await app.listen(0);
    base = `http://127.0.0.1:${app.getHttpServer().address().port}`;
  });
  afterAll(async () => { await app?.close(); });

  it('allows a company account to search HS codes', async () => {
    const response = await fetch(`${base}/api/hs-codes/search?q=6109`, { headers: headers() });
    expect(response.status).toBe(200);
    expect((await response.json())[0].code).toBe('61091010');
  });
  it('reports database readiness to Render', async () => {
    const response = await fetch(`${base}/api/health`);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok' });
  });
  it('validates classification input', async () => {
    const response = await fetch(`${base}/api/classification/search`, { method: 'POST', headers: headers(), body: JSON.stringify({ description: 123 }) });
    expect(response.status).toBe(400);
  });
  it.each([
    ['GET', '/hs-codes/search?q=6109'], ['GET', '/hs-codes/61091010'],
    ['POST', '/classification/search'], ['POST', '/classification/prepare-items'],
    ['POST', '/classification/extract'], ['GET', '/classification/saved'],
    ['POST', '/classification/saved/feedback'], ['GET', '/classification/history'],
    ['GET', '/admin/documents'], ['GET', '/auth/me'],
  ])('requires login for %s %s', async (method, path) => {
    expect((await fetch(`${base}/api${path}`, { method })).status).toBe(401);
  });

  it.each(['/auth/me', '/hs-codes/search?q=6109', '/classification/saved', '/admin/documents'])(
    'rejects a legacy token from an external account at %s', async path => {
      expect((await fetch(`${base}/api${path}`, { headers: headers(external.id, 'ADMIN') })).status).toBe(403);
    },
  );

  it('normalizes login email and returns an authenticated company session', async () => {
    const response = await fetch(`${base}/api/auth/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: ' MEMBER@UNIGROUP.COM.VN ', password: 'correct-password' }) });
    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.user).toEqual({ sub: member.id, email: member.email, role: 'USER' });
    expect((await fetch(`${base}/api/auth/me`, { headers: { authorization: `Bearer ${data.access_token}` } })).status).toBe(200);
  });

  it.each(['login', 'register'])('rejects external email at /auth/%s', async action => {
    const response = await fetch(`${base}/api/auth/${action}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: external.email, password: 'correct-password' }) });
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ code: 'EMAIL_DOMAIN_NOT_ALLOWED' });
  });

  it('uses the current database role to protect admin access', async () => {
    expect((await fetch(`${base}/api/admin/documents`, { headers: headers(member.id, 'ADMIN') })).status).toBe(403);
    expect((await fetch(`${base}/api/admin/documents`, { headers: headers(admin.id) })).status).toBe(200);
  });

  it('does not expose another user’s saved result', async () => {
    expect((await fetch(`${base}/api/classification/saved`, { headers: headers() })).status).toBe(404);
  });
});
