import { Test } from '@nestjs/testing';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './module';
import { Database } from './database';

describe('HTTP API', () => {
  let app: any; let base: string;
  beforeAll(async () => {
    process.env.JWT_SECRET = 'a-very-long-test-secret-at-least-32-characters';
    const db = { $queryRaw: jest.fn().mockResolvedValue([{ ok: 1 }]), hsCode: { findMany: jest.fn().mockResolvedValue([{ code: '61091010', description: 'Áo phông nam' }]) } };
    const module = await Test.createTestingModule({ imports: [AppModule] }).overrideProvider(Database).useValue(db).compile();
    app = module.createNestApplication();
    app.setGlobalPrefix('api');
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
    await app.listen(0);
    base = `http://127.0.0.1:${app.getHttpServer().address().port}`;
  });
  afterAll(async () => { await app?.close(); });

  it('searches HS code through the public endpoint', async () => {
    const response = await fetch(`${base}/api/hs-codes/search?q=6109`);
    expect(response.status).toBe(200);
    expect((await response.json())[0].code).toBe('61091010');
  });
  it('reports database readiness to Render', async () => {
    const response = await fetch(`${base}/api/health`);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok' });
  });
  it('validates classification input', async () => {
    const response = await fetch(`${base}/api/classification/search`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ description: ' ' }) });
    expect(response.status).toBe(400);
  });
  it('protects history and admin endpoints', async () => {
    expect((await fetch(`${base}/api/classification/history`)).status).toBe(401);
    expect((await fetch(`${base}/api/admin/documents`)).status).toBe(401);
  });
});
