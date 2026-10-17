import { ClassificationService } from './classification';
import { AuthService, type AuthRequest } from '../auth/auth';
import { Database } from '../database';
import { HsCodesService } from '../hs-codes/hs-codes';

describe('classification history', () => {
  const session = { sub: 'member-1', email: 'member@unigroup.com.vn', role: 'USER' as const };

  it('includes legacy unowned searches by default and paginates in a stable order', async () => {
    const findMany = jest.fn().mockResolvedValue([]);
    const auth = { verify: jest.fn().mockResolvedValue(session) } as unknown as AuthService;
    const service = new ClassificationService({ classificationSearch: { findMany } } as unknown as Database, {} as HsCodesService, auth);
    await service.history({ headers: {} } as AuthRequest, 2);
    expect(auth.verify).toHaveBeenCalled();
    expect(findMany).toHaveBeenCalledWith(expect.objectContaining({
      where: { OR: [{ userId: session.sub }, { userId: null }] },
      orderBy: [{ createdAt: 'desc' }, { id: 'desc' }], skip: 20, take: 20,
    }));
  });

  it.each([
    ['mine', { userId: session.sub }],
    ['legacy', { userId: null }],
  ] as const)('applies the %s scope without changing search ownership', async (scope, where) => {
    const findMany = jest.fn().mockResolvedValue([]);
    const update = jest.fn();
    const service = new ClassificationService({ classificationSearch: { findMany, update } } as unknown as Database, {} as HsCodesService, {} as AuthService);
    await service.history({ session } as AuthRequest, 1, scope);
    expect(findMany).toHaveBeenCalledWith(expect.objectContaining({ where, skip: 0 }));
    expect(update).not.toHaveBeenCalled();
  });
});
