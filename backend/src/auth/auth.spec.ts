import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';
import { AuthService, type AuthRequest } from './auth';
import { Database } from '../database';

describe('authentication', () => {
  beforeAll(() => { process.env.JWT_SECRET = 'a-very-long-test-secret-at-least-32-characters'; });
  const request = (token?: string) => ({ headers: token ? { authorization: `Bearer ${token}` } : {} }) as AuthRequest;
  const sign = (claims: object = { sub: 'user-1', role: 'USER' }, options: jwt.SignOptions = {}) => jwt.sign(claims, process.env.JWT_SECRET!, options);

  it('normalizes company email and registers normal users, never admins', async () => {
    const create = jest.fn().mockResolvedValue({ id: 'user-1', role: 'USER' });
    const service = new AuthService({ user: { findUnique: jest.fn().mockResolvedValue(null), create } } as unknown as Database);
    const token = await service.register({ email: ' EXAMPLE@UNIGROUP.COM.VN ', password: 'strong-password' });
    expect(create.mock.calls[0][0].data.email).toBe('example@unigroup.com.vn');
    expect(create.mock.calls[0][0].data.role).toBeUndefined();
    expect(await bcrypt.compare('strong-password', create.mock.calls[0][0].data.passwordHash)).toBe(true);
    expect(token.role).toBe('USER');
    expect(token.user.email).toBe('example@unigroup.com.vn');
    expect(jwt.verify(token.access_token, process.env.JWT_SECRET!)).toMatchObject(token.user);
  });

  it.each(['user@gmail.com', 'user@sub.unigroup.com.vn', 'user@unigroup.com.vn.evil.com', 'user@evilunigroup.com.vn', 'user@@unigroup.com.vn', '@unigroup.com.vn'])(
    'rejects registration and login for %s before accessing the database', async email => {
      const findUnique = jest.fn(); const create = jest.fn();
      const service = new AuthService({ user: { findUnique, create } } as unknown as Database);
      await expect(service.register({ email, password: 'strong-password' })).rejects.toMatchObject({ status: 403 });
      await expect(service.login({ email, password: 'strong-password' })).rejects.toMatchObject({ status: 403 });
      expect(findUnique).not.toHaveBeenCalled();
      expect(create).not.toHaveBeenCalled();
    },
  );

  it('requires the correct password for a company account', async () => {
    const user = { id: 'user-1', email: 'member@unigroup.com.vn', role: 'USER', passwordHash: await bcrypt.hash('correct-password', 4) };
    const findUnique = jest.fn().mockResolvedValue(user);
    const service = new AuthService({ user: { findUnique } } as unknown as Database);
    await expect(service.login({ email: ' MEMBER@UNIGROUP.COM.VN ', password: 'correct-password' })).resolves.toMatchObject({ user: { email: user.email } });
    expect(findUnique).toHaveBeenCalledWith({ where: { email: user.email } });
    await expect(service.login({ email: user.email, password: 'wrong-password' })).rejects.toMatchObject({ status: 401 });
  });

  it('requires a valid, unexpired token for private endpoints', async () => {
    const service = new AuthService({} as Database);
    for (const token of [undefined, 'invalid', sign({}, {}), sign({ sub: 'user-1' }, { expiresIn: -1 }), sign({ sub: 'user-1' }, { algorithm: 'HS384' })]) {
      await expect(service.verify(request(token))).rejects.toMatchObject({ status: 401 });
    }
  });

  it('checks current database email and role, including tokens issued before the domain restriction', async () => {
    const user = { id: 'user-1', email: 'member@unigroup.com.vn', role: 'USER' };
    const findUnique = jest.fn().mockResolvedValue(user);
    const service = new AuthService({ user: { findUnique } } as unknown as Database);
    const oldAdminToken = sign({ sub: user.id, role: 'ADMIN' });
    await expect(service.verify(request(oldAdminToken))).resolves.toEqual({ sub: user.id, email: user.email, role: 'USER' });
    findUnique.mockResolvedValue({ ...user, email: 'member@example.com', role: 'ADMIN' });
    await expect(service.verify(request(oldAdminToken))).rejects.toMatchObject({ status: 403 });
    findUnique.mockResolvedValue(null);
    await expect(service.verify(request(oldAdminToken))).rejects.toMatchObject({ status: 401 });
  });
});
