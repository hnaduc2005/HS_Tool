import { AuthService } from './auth';
import { Database } from '../database';

describe('authentication', () => {
  beforeAll(() => { process.env.JWT_SECRET = 'a-very-long-test-secret-at-least-32-characters'; });
  it('registers normal users, never admins', async () => {
    const create = jest.fn().mockResolvedValue({ id: 'user-1', role: 'USER' });
    const service = new AuthService({ user: { findUnique: jest.fn().mockResolvedValue(null), create } } as unknown as Database);
    const token = await service.register({ email: 'EXAMPLE@TEST.COM', password: 'strong-password' });
    expect(create.mock.calls[0][0].data.email).toBe('example@test.com');
    expect(create.mock.calls[0][0].data.role).toBeUndefined();
    expect(token.role).toBe('USER');
  });
  it('requires a valid token for private endpoints', () => {
    const service = new AuthService({} as Database);
    expect(() => service.verify({ headers: {} } as any, true)).toThrow();
  });
});
