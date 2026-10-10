import { HsCodesService } from './hs-codes';
import { Database } from '../database';

describe('HS search', () => {
  it('retains other decorative paper alongside coating branches despite a wrong hint and candidate cap', async () => {
    const rows = Array.from({ length: 60 }, (_, index) => ({ code: `480255${String(index).padStart(2, '0')}`, description: `Giấy chưa tráng ${index}` }));
    rows.push(
      { code: '4811', description: 'Giấy đã tráng, thấm tẩm, phủ hoặc trang trí bề mặt' },
      { code: '481159', description: 'Giấy phủ bằng plastic: → Loại khác' },
      { code: '48115999', description: 'Loại khác' },
      { code: '481190', description: 'Giấy khác' },
      { code: '48119049', description: 'Khổ cuộn không quá 15 cm: → Loại khác' },
      { code: '48119099', description: 'Loại khác: → Loại khác' },
    );
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const result = await service.candidates('Giấy trang trí phủ PU, QC: 1270MM *30G~45G, dùng dán giả vân gỗ trên bề mặt ván', { heading_hints: ['480255', '48115999'] });
    expect(result.length).toBeLessThanOrEqual(50);
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['48115999', '48119049', '48119099']));
    expect(result.find(row => row.code === '48119099')!.description).toContain('Giấy khác');
  });
  it('expands the whole textile family despite a wrong flat-knitting hint and retains the last national child', async () => {
    const rows = [
      { code: '8447', description: 'Máy dệt kim, máy khâu đính và máy sản xuất ren, trang trí' },
      { code: '84471100', description: 'Máy dệt kim tròn: → Có đường kính trục cuốn không quá 165 mm' },
      { code: '84471200', description: 'Máy dệt kim tròn: → Có đường kính trục cuốn trên 165 mm' },
      { code: '844720', description: '- Máy dệt kim phẳng; máy khâu đính:' },
      { code: '84472010', description: '- - Hoạt động bằng điện' },
      { code: '84472020', description: '- - Không hoạt động bằng điện' },
      { code: '844790', description: '- Loại khác:' },
      { code: '84479010', description: '- - Hoạt động bằng điện' },
      { code: '84479020', description: '- - Không hoạt động bằng điện' },
    ];
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const raw = jest.fn().mockImplementation(async (_sql, phrase) => phrase === 'máy dệt kim' ? [{ ...rows[0], score: .95 }] : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: raw } as unknown as Database);
    const result = await service.candidates('COMPUTERIZED CROCHET MACHINE, MODEL: B16 20, POWER: 1.5KW', { heading_hints: ['84472010'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['84479010', '84479020', '84472010']));
    expect(result.find(row => row.code === '84479010')!.description).toContain('→ Loại khác: → Hoạt động bằng điện');
  });
  it('finds static converter siblings despite an incorrect transformer hint and a large candidate pool', async () => {
    const rows = Array.from({ length: 60 }, (_, index) => ({ code: `850421${String(index).padStart(2, '0')}`, description: `Biến áp công dụng ${index}: → Loại khác` }));
    rows.push(
      { code: '850421', description: 'Máy biến điện sử dụng điện môi lỏng' },
      { code: '850440', description: '- Máy biến đổi tĩnh điện:' },
      { code: '85044030', description: '- - Bộ chỉnh lưu khác' },
      { code: '85044040', description: '- - Bộ nghịch lưu' },
      { code: '85044090', description: '- - Loại khác' },
    );
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const raw = jest.fn().mockImplementation(async (_sql, phrase) => phrase === 'máy biến đổi tĩnh điện'
      ? [{ ...rows[61], score: 1 }] : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: raw } as unknown as Database);
    const result = await service.candidates('INVERTER, MODEL: JK200A-075-4T', { heading_hints: ['85042199', '850421'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['85044030', '85044040', '85044090']));
    expect(result.find(row => row.code === '85044090')!.description).toContain('Máy biến đổi tĩnh điện');
  });
  it('normalizes dash labels and retains material siblings when there are over 50 branch leads', async () => {
    const rows = Array.from({ length: 60 }, (_, index) => ({ code: `848180${String(index).padStart(2, '0')}`, description: `Chuyên dùng ${index}: → - - Loại khác` }));
    rows.push(
      { code: '848120', description: 'Van dùng trong truyền động dầu thủy lực hoặc khí nén' },
      { code: '84812011', description: '- - Van cổng điều khiển bằng tay: → Bằng sắt hoặc thép' },
      { code: '84812019', description: '- - Van cổng điều khiển bằng tay: → Loại khác' },
      { code: '84812020', description: '- - Bằng đồng có đường kính trong nhỏ' },
      { code: '84812090', description: '- - Loại khác' },
    );
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const raw = jest.fn().mockResolvedValue([{ ...rows[60], score: 1 }]);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: raw } as unknown as Database);
    const result = await service.candidates('PNEUMATIC VALVE φ350', { heading_hints: ['8481'] });
    expect(result.length).toBeLessThanOrEqual(50);
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['84812011', '84812019', '84812090']));
    expect(result.find(row => row.code === '84812090')!.description).toMatch(/→ Loại khác$/);
  });
  it('expands an AI eight-digit guess to siblings instead of hiding the parent residual', async () => {
    const rows = [
      { code: '84812011', description: 'Van cổng điều khiển bằng tay: → Bằng sắt hoặc thép' },
      { code: '84812019', description: 'Van cổng điều khiển bằng tay: → Loại khác' },
      { code: '84812090', description: 'Loại khác' },
    ];
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.startsWith
      ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const result = await service.candidates('PNEUMATIC VALVE φ350', { heading_hints: ['84812019'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['84812011', '84812019', '84812090']));
  });
  it('preserves parent residual and nested residual valve branches under the candidate cap', async () => {
    const rows = Array.from({ length: 60 }, (_, index) => ({ code: `848110${String(index).padStart(2, '0')}`, description: 'Van giảm áp' }));
    rows.push(
      { code: '84812011', description: 'Van cổng điều khiển bằng tay: → Bằng sắt hoặc thép' },
      { code: '84812019', description: 'Van cổng điều khiển bằng tay: → Loại khác' },
      { code: '84812090', description: 'Loại khác' },
    );
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.startsWith
      ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const result = await service.candidates('PNEUMATIC VALVE φ350', { heading_hints: ['8481'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['84812019', '84812090']));
  });
  it('preserves late national power ranges when a broad heading has many early children', async () => {
    const rows = Array.from({ length: 50 }, (_, index) => ({ code: `850110${String(index).padStart(2, '0')}`, description: 'Động cơ nhỏ' }));
    rows.push(
      { code: '85015229', description: 'Động cơ xoay chiều khác, đa pha: → Công suất trên 1 kW nhưng không quá 37,5 kW: → Loại khác' },
      { code: '85015239', description: 'Động cơ xoay chiều khác, đa pha: → Công suất trên 37,5 kW nhưng không quá 75 kW: → Loại khác' },
      { code: '85015390', description: 'Động cơ xoay chiều khác, đa pha: → Công suất trên 75 kW: → Loại khác' },
    );
    const findMany = jest.fn().mockImplementation(async query => query.where.code?.startsWith
      ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)).slice(0, query.take) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const result = await service.candidates('HIGH EFFICIENCY PERMANENT MAGNET SYNCHRONOUS SERVO MOTOR', { heading_hints: ['8501'] });
    expect(result.length).toBeLessThanOrEqual(50);
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['85015229', '85015239', '85015390']));
  });
  it('uses exact code prefix for numeric queries', async () => {
    const findMany = jest.fn().mockResolvedValue([{ code: '61091010', description: 'Áo phông nam' }]);
    const service = new HsCodesService({ hsCode: { findMany } } as unknown as Database);
    const result = await service.search('6109.10', 20);
    expect(findMany).toHaveBeenCalledWith(expect.objectContaining({ where: { isActive: true, code: { startsWith: '610910' } } }));
    expect(result[0].code).toBe('61091010');
  });
  it('parameterizes text searches', async () => {
    const raw = jest.fn().mockResolvedValue([]);
    const service = new HsCodesService({ $queryRawUnsafe: raw } as unknown as Database);
    await service.search("áo thun' OR true --");
    expect(raw.mock.calls[0][1]).toBe("áo thun' OR true --");
    expect(raw.mock.calls[0][0]).not.toContain("áo thun' OR true --");
  });
  it('expands AI heading hints for a mixed prepared food', async () => {
    const rows = [
      { code: '1605', description: 'Động vật giáp xác đã chế biến' },
      { code: '160529', description: 'Loại khác' },
      { code: '16052990', description: 'Loại khác' },
      { code: '1602', description: 'Thịt đã chế biến' },
      { code: '1904', description: 'Chế phẩm từ ngũ cốc' },
      { code: '19049010', description: 'Chế phẩm từ gạo' },
    ];
    const findMany = jest.fn().mockImplementation(async (query) => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const result = await service.candidates('Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%',
      { heading_hints: ['1605', '1602', '1904'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['16052990', '1602', '19049010']));
    expect(result.find(row => row.code === '16052990')?.description).toContain('Động vật giáp xác đã chế biến');
  });
  it('finds wooden furniture candidates for a bilingual dining table description', async () => {
    const rows = [
      { code: '9403', description: 'Đồ nội thất khác và các bộ phận của chúng' },
      { code: '94034000', description: 'Đồ nội thất bằng gỗ loại sử dụng trong nhà bếp' },
      { code: '940360', description: 'Đồ nội thất bằng gỗ khác' },
      { code: '94036090', description: 'Loại khác' },
    ];
    const findMany = jest.fn().mockImplementation(async (query) => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([{ code: '94036090', description: 'Loại khác' }]) } as unknown as Database);
    const result = await service.candidates('CG-200 WOOD DINING TABLE- Bàn ăn CG-200 QC:(1829*914*762H)mm',
      { queries: ['đồ nội thất bằng gỗ khác'], heading_hints: ['9403', '94036090'] });
    expect(result.map(row => row.code)).toEqual(expect.arrayContaining(['9403', '94034000', '94036090']));
    expect(result.find(row => row.code === '94036090')?.score).toBeGreaterThan(0.8);
  });
  it('uses AI search hints for the CG-300 TV console description', async () => {
    const rows = [
      { code: '9403', description: 'Đồ nội thất khác' },
      { code: '940360', description: 'Đồ nội thất bằng gỗ khác' },
      { code: '94036090', description: 'Loại khác' },
    ];
    const findMany = jest.fn().mockImplementation(async (query) => query.where.code?.in ? rows.filter(row => query.where.code.in.includes(row.code))
      : query.where.code?.startsWith ? rows.filter(row => row.code.startsWith(query.where.code.startsWith)) : []);
    const service = new HsCodesService({ hsCode: { findMany }, $queryRawUnsafe: jest.fn().mockResolvedValue([]) } as unknown as Database);
    const description = 'CG-300 TV CONSOLE- Kệ TV CG-300 QC:(1524*457*864H)mm,(gỗ ghép (gỗ dương),ván MDF,ván ép),không nhãn hiệu,có nhãn hàng hóa,mới100%';
    const result = await service.candidates(description,
      { queries: ['đồ nội thất bằng gỗ khác', 'kệ ti vi bằng gỗ'], heading_hints: ['9403', '940360'] });
    expect(result.map(row => row.code)).toContain('94036090');
    expect(result.find(row => row.code === '94036090')?.description).toContain('Đồ nội thất bằng gỗ khác');
    expect(result.find(row => row.code === '94036090')?.score).toBeGreaterThan(0.85);
  });
});
