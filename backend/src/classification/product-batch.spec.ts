import { ClassificationService } from './classification';
import { aiCall } from '../ai/client';
import { Database } from '../database';
import { HsCodesService } from '../hs-codes/hs-codes';
import { AuthService } from '../auth/auth';

jest.mock('../ai/client', () => ({ aiCall: jest.fn() }));
describe('multi-product preparation', () => {
  beforeEach(() => jest.clearAllMocks());
  it('passes the full list to item recognition without classifying or assigning shared declarations', async () => {
    const text = '1. COMPUTERIZED CROCHET MACHINE\nMODEL B16 20\nPOWER 1.5KW\n\n2. INVERTER MODEL JK200A';
    const expected = { items: [{ description: 'COMPUTERIZED CROCHET MACHINE\nMODEL B16 20\nPOWER 1.5KW' }, { description: 'INVERTER MODEL JK200A' }], needs_review: false, message: '' };
    (aiCall as jest.Mock).mockResolvedValue(expected);
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    const db = { classificationSearch: { create: jest.fn() } } as unknown as Database;
    const service = new ClassificationService(db, {} as HsCodesService, auth);
    expect(await service.prepareItems(text, { ip: 'batch-prepare' } as any)).toEqual(expected);
    expect(aiCall).toHaveBeenCalledWith('/prepare-items', { description: text }, 120000);
    expect(db.classificationSearch.create).not.toHaveBeenCalled();
    expect(auth.verify).toHaveBeenCalled();
  });
  it('rejects empty input before calling the model', async () => {
    const service = new ClassificationService({} as Database, {} as HsCodesService, { verify: () => undefined } as unknown as AuthService);
    await expect(service.prepareItems(' ', { ip: 'batch-empty' } as any)).rejects.toMatchObject({ status: 400 });
    expect(aiCall).not.toHaveBeenCalled();
  });
});
