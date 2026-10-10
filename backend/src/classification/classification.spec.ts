import { ClassificationService } from './classification';
import { Database } from '../database';
import { HsCodesService } from '../hs-codes/hs-codes';
import { AuthService } from '../auth/auth';
import { aiCall } from '../ai/client';
import { tariffRatesFor } from '../hs-codes/tariff-rates';
import { HttpException, HttpStatus } from '@nestjs/common';

jest.mock('../ai/client', () => ({ aiCall: jest.fn() }));
describe('classification guardrails', () => {
  it('preserves a supported first proposal when catalog recovery returns no usable code', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-keep', documentId: 'doc-keep', page: 1, content: '48.11 - Giấy đã trang trí bề mặt', document: { title: 'Chú giải', source: 'Nguồn thử' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValueOnce([{ code: '48119099', description: 'Giấy khác, loại khác' }])
      .mockResolvedValueOnce([{ code: '48115999', description: 'Giấy phủ plastic, loại khác' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    let analyses = 0;
    (aiCall as jest.Mock).mockImplementation(async route => {
      if (route === '/discover-candidates') return {};
      if (++analyses === 2) return { status: 'INSUFFICIENT_EVIDENCE', legal_analysis: { hypotheses: [] } };
      return { status: 'CONDITIONAL', normalized_product: {}, missing_information: ['Khổ giấy'],
        catalog_hints: { heading_hints: ['4811'] },
        sources: [{ chunk_id: 'chunk-keep', document_id: 'doc-keep', page: 1, relevance_score: .8 }],
        legal_analysis: { legal_steps: [{ rule: 'Quy tắc 6', application: 'Đối chiếu nhánh kích thước.', source_chunk_ids: ['chunk-keep'] }],
          hypotheses: [{ code: '48119099', label: 'Khổ lớn', assumptions: ['Khổ giấy trên 36 cm'], reasoning: 'Giấy trang trí bề mặt, khổ lớn.', source_chunk_ids: ['chunk-keep'] }] } };
    });
    const result = await new ClassificationService(db, hs, auth).search('Giấy trang trí phủ PU dùng dán bề mặt ván', { ip: 'retain-proposal' } as any);
    expect(analyses).toBe(2);
    expect(result.status).toBe('CONDITIONAL');
    expect(create.mock.calls[0][0].data.legalAnalysis.hypotheses[0].code).toBe('48119099');
    expect(create.mock.calls[0][0].data.normalizedProduct.provisional_code).toBe('48119099');
  });
  it('does not save an AI outage as missing product evidence', async () => {
    const create = jest.fn();
    const db = { classificationSearch: { create } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockRejectedValue(new HttpException('AI_SERVICE_UNAVAILABLE', HttpStatus.SERVICE_UNAVAILABLE));
    await expect(new ClassificationService(db, hs, auth).search('Kệ TV bằng gỗ ghép và ván MDF', { ip: 'outage-test' } as any))
      .rejects.toMatchObject({ status: HttpStatus.SERVICE_UNAVAILABLE });
    expect(create).not.toHaveBeenCalled();
  });
  it('continues legal analysis when catalog search finds no candidates', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-1', documentId: 'doc-1', page: 1, content: 'Quy tắc 1: phân loại theo nội dung nhóm.', document: { title: 'Quy tắc tổng quát', source: 'Nguồn thử' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockImplementation(async (route) => route === '/discover-candidates'
      ? { queries: ['đồ nội thất bằng gỗ'], heading_hints: ['9403'] }
      : { status: 'INSUFFICIENT_EVIDENCE', normalized_product: { product_name: 'Kệ TV' }, missing_information: ['Cần đối chiếu mã tám số'],
          sources: [{ chunk_id: 'chunk-1', document_id: 'doc-1', page: 1, relevance_score: .7 }],
          legal_analysis: { summary: 'Đã xét Quy tắc 1.', product_facts: ['Kệ TV'],
            legal_steps: [{ rule: 'Quy tắc 1', application: 'Xét nội dung nhóm phù hợp.', source_chunk_ids: ['chunk-1'] }],
            alternatives: [], conclusion: 'Cần đối chiếu mã tám số.', limitations: [] } });
    const result = await new ClassificationService(db, hs, auth).search('Kệ TV bằng gỗ ghép, ván MDF và ván ép', { ip: 'no-candidates' } as any);
    expect(hs.candidates).toHaveBeenCalledWith(expect.any(String), { queries: ['đồ nội thất bằng gỗ'], heading_hints: ['9403'] });
    expect(aiCall).toHaveBeenCalledWith('/classify', expect.objectContaining({ candidates: [] }), 240000);
    expect(result.status).toBe('INSUFFICIENT_EVIDENCE');
    expect(create.mock.calls[0][0].data.legalAnalysis.legal_steps).toHaveLength(1);
  });
  it('does not persist an invented code as a result', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const db = { classificationSearch: { create } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([{ code: '61091010', description: 'Áo phông nam' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockResolvedValue({ status: 'COMPLETED', recommended_code: '99999999', normalized_product: {}, missing_information: [] });
    const service = new ClassificationService(db, hs, auth);
    const result = await service.search('Áo thun nam 100% cotton', { ip: 'test-ip' } as any);
    expect(result.status).toBe('INSUFFICIENT_EVIDENCE');
    expect(create.mock.calls[0][0].data.results).toBeUndefined();
    expect(create.mock.calls[0][0].data.legalAnalysis.conclusion).toBeTruthy();
  });
  it('does not mark a six-digit parent as a completed Vietnamese declaration code', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-1', documentId: 'doc-1', page: 1, content: '9403.60 - Đồ nội thất bằng gỗ khác', document: { title: 'Danh mục HS', source: 'Nguồn thử' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([{ code: '940360', description: 'Đồ nội thất bằng gỗ khác' }, { code: '94036090', description: 'Loại khác' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockImplementation(async (route) => route === '/discover-candidates' ? {}
      : { status: 'COMPLETED', recommended_code: '940360', normalized_product: {}, missing_information: [],
          sources: [{ chunk_id: 'chunk-1', document_id: 'doc-1', page: 1, relevance_score: .8 }],
          legal_analysis: { legal_steps: [{ rule: 'Quy tắc 6', application: 'Phân nhóm 9403.60.', source_chunk_ids: ['chunk-1'] }] } });
    const result = await new ClassificationService(db, hs, auth).search('Kệ TV bằng gỗ ghép và ván MDF', { ip: 'six-digit-test' } as any);
    expect(result.status).toBe('INSUFFICIENT_EVIDENCE');
    expect(create.mock.calls[0][0].data.results).toBeUndefined();
    expect(result.missingInformation).toEqual(expect.arrayContaining([expect.stringContaining('8 số')]));
  });
  it('preserves a verified legal explanation when the result is conditional', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-1', documentId: 'doc-1', page: 76, content: 'Chú giải 2 Chương 16', document: { title: 'Nghị định 26/2023', source: 'https://congbao.chinhphu.vn/' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([{ code: '16052990', description: 'Tôm chế biến, loại khác' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockResolvedValue({ status: 'INSUFFICIENT_EVIDENCE', normalized_product: { provisional_code: '16052990' },
      missing_information: ['Cần xác nhận 10% thành phần'], sources: [{ chunk_id: 'chunk-1', document_id: 'doc-1', page: 76, relevance_score: .9 }],
      legal_analysis: { summary: 'Phần đã khai có 21% tôm và thịt.', product_facts: ['Tôm 11%, thịt 10%'],
        legal_steps: [{ rule: 'Chú giải 2 Chương 16', application: '21% vượt 20%', source_chunk_ids: ['chunk-1', 'invented'] }],
        alternatives: [], conclusion: 'Mã chỉ có điều kiện.', limitations: ['Thiếu 10% thành phần'] } });
    const service = new ClassificationService(db, hs, auth);
    const result = await service.search('Cơm chiên gạo 55%, tôm 11%, thịt 10%', { ip: 'conditional-test' } as any);
    expect(result.status).toBe('INSUFFICIENT_EVIDENCE');
    const analysis = create.mock.calls[0][0].data.legalAnalysis;
    expect(analysis.legal_steps[0].source_chunk_ids).toEqual(['chunk-1']);
    expect(analysis.references[0].title).toBe('Nghị định 26/2023');
    expect(analysis.tariff_rates).toEqual(tariffRatesFor('16052990'));
    expect(analysis.tariff_rates?.akfta).toBe('0');
    expect(analysis.tariff_rates?.vat).toBe('8/10');
  });
  it('downgrades a model-completed answer when its material is still an explicit hypothesis', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-1', documentId: 'doc-1', page: 1, content: '9403.60 Đồ nội thất bằng gỗ; 9403.70 Đồ nội thất bằng plastic', document: { title: 'Danh mục HS', source: 'Nguồn thử' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } as any } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([{ code: '94036090', description: 'Đồ nội thất bằng gỗ khác' }, { code: '94037090', description: 'Đồ nội thất bằng plastic khác' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    const wood = { code: '94036090', label: 'Bằng gỗ', assumptions: ['Kệ TV bằng gỗ'], reasoning: 'Đối chiếu nhánh đồ nội thất bằng gỗ khác.', source_chunk_ids: ['chunk-1'] };
    const plastic = { code: '94037090', label: 'Bằng plastic', assumptions: ['Kệ TV bằng plastic'], reasoning: 'Đối chiếu nhánh đồ nội thất bằng plastic khác.', source_chunk_ids: ['chunk-1'] };
    (aiCall as jest.Mock).mockImplementation(async (route) => route === '/discover-candidates' ? {}
      : { status: 'COMPLETED', recommended_code: '94036090', normalized_product: { provisional_code: '99999999' }, missing_information: ['Chưa nêu vật liệu'],
          sources: [{ chunk_id: 'chunk-1', document_id: 'doc-1', page: 1, relevance_score: .8 }],
          legal_analysis: { legal_steps: [{ rule: 'Quy tắc 6', application: 'So sánh các phân nhóm theo vật liệu.', source_chunk_ids: ['chunk-1'] }],
            hypotheses: [wood, plastic, { ...wood, code: '940360' }, { ...wood, code: '99999999' }, { ...wood, assumptions: [] }, { ...wood, source_chunk_ids: ['invented'] }] } });
    const result = await new ClassificationService(db, hs, auth).search('Kệ TV dùng trong phòng khách, chưa nêu vật liệu', { ip: 'hypothesis-test' } as any);
    const saved = create.mock.calls[0][0].data;
    expect(result.status).toBe('CONDITIONAL');
    expect(saved.normalizedProduct.provisional_code).toBe('94036090');
    expect(saved.legalAnalysis.hypotheses.map((h: any) => h.code)).toEqual(['94036090', '94037090']);
    expect(saved.legalAnalysis.hypotheses[0].tariff_rates).toEqual(tariffRatesFor('94036090'));
    expect(saved.legalAnalysis.hypotheses[0].catalog_description).toBe('Đồ nội thất bằng gỗ khác');
    expect(saved.legalAnalysis.tariff_rates.code).toBe('94036090');
    expect(saved.results).toBeUndefined();
  });
  it('checks catalog branches indicated by legal analysis before saving conditional proposals', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunk = { id: 'chunk-1', documentId: 'doc-1', page: 1, content: 'Chú giải 2 Chương 16', document: { title: 'Chú giải pháp lý', source: 'Nguồn thử' } };
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue([chunk]) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValueOnce([{ code: '19049010', description: 'Chế phẩm từ gạo' }])
      .mockResolvedValueOnce([{ code: '16052990', description: 'Tôm chế biến khác' }, { code: '16024991', description: 'Thịt lợn chế biến khác, kín khí để bán lẻ' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    const recovery = { heading_hints: ['16052990', '160249'], queries: ['chế phẩm tôm', 'thịt lợn chế biến'] };
    let analyses = 0;
    (aiCall as jest.Mock).mockImplementation(async (route) => {
      if (route === '/discover-candidates') return {};
      if (++analyses === 1) return { status: 'INSUFFICIENT_EVIDENCE', catalog_hints: recovery };
      return { status: 'INSUFFICIENT_EVIDENCE', normalized_product: {}, missing_information: ['Thiếu 10% thành phần'],
        sources: [{ chunk_id: 'chunk-1', document_id: 'doc-1', page: 1, relevance_score: .8 }],
        legal_analysis: { legal_steps: [{ rule: 'Chú giải 2 Chương 16', application: 'Tổng 21% và so sánh thành phần động vật.', source_chunk_ids: ['chunk-1'] }],
          hypotheses: [{ code: '16052990', label: 'Tôm chiếm ưu thế', assumptions: ['Phần còn lại là rau củ'], reasoning: 'Tôm 11% lớn hơn thịt 10%.', source_chunk_ids: ['chunk-1'] },
            { code: '16024991', label: 'Thịt lợn chiếm ưu thế', assumptions: ['Phần còn lại là thịt lợn', 'Hộp để bán lẻ'], reasoning: 'Thịt lợn 20% lớn hơn tôm 11%.', source_chunk_ids: ['chunk-1'] }] } };
    });
    await new ClassificationService(db, hs, auth).search('Cơm chiên hộp kín khí: gạo 55%, tôm 11%, thịt lợn 10%, còn thiếu 10%', { ip: 'recovery-test' } as any);
    const saved = create.mock.calls[0][0].data;
    expect(hs.candidates).toHaveBeenNthCalledWith(2, expect.any(String), recovery);
    expect(analyses).toBe(2);
    expect(saved.legalAnalysis.hypotheses.map((h: any) => h.code)).toEqual(['16052990', '16024991']);
    expect(saved.normalizedProduct.provisional_code).toBe('16052990');
  });
  it('accepts feedback for an anonymous search ID', async () => {
    const create = jest.fn().mockResolvedValue({ id: 'feedback-1' });
    const db = { classificationSearch: { findUnique: jest.fn().mockResolvedValue({ id: 'search-1', userId: null, results: [{ id: 'result-1' }] }) }, feedback: { create } } as unknown as Database;
    const service = new ClassificationService(db, {} as HsCodesService, { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService);
    await service.feedback('search-1', { is_correct: true }, { ip: 'feedback-test' } as any);
    expect(create.mock.calls[0][0].data.resultId).toBe('result-1');
  });
  it('persists conditional questions and both article codes for a gift classified separately', async () => {
    const create = jest.fn().mockImplementation(({ data }) => Promise.resolve({ ...data, results: [] }));
    const chunks = ['rule', 'tie', 'sock'].map(id => ({ id, documentId: 'doc-1', page: 8, content: id, document: { title: 'Căn cứ', source: 'Nguồn thử' } }));
    const db = { classificationSearch: { create }, documentChunk: { findMany: jest.fn().mockResolvedValue(chunks) } } as unknown as Database;
    const hs = { candidates: jest.fn().mockResolvedValue([{ code: '62152090', description: 'Cà vạt sợi nhân tạo, loại khác' }, { code: '61159500', description: 'Bít tất dệt kim từ bông' }]) } as unknown as HsCodesService;
    const auth = { verify: jest.fn().mockReturnValue(undefined) } as unknown as AuthService;
    (aiCall as jest.Mock).mockImplementation(async route => route === '/discover-candidates' ? {} : {
      status: 'CONDITIONAL', normalized_product: { provisional_code: '62152090' }, missing_information: ['Chất liệu chưa khai'],
      legal_analysis: { summary: 'Chưa đủ căn cứ để xác định một mã duy nhất.',
        decision_questions: [{ question: 'Hai món có tạo thành bộ bán lẻ không?', answer: 'Giả định không đáp ứng: phân loại riêng.', source_chunk_ids: ['rule', 'invented'] }],
        legal_steps: [{ rule: 'Quy tắc 1', application: 'Xét riêng từng mặt hàng.', source_chunk_ids: ['rule'] }],
        hypotheses: [{ code: '62152090', label: 'Cà vạt polyester và vớ cotton', classification_mode: 'separate',
          assumptions: ['Cà vạt polyester không in batik', 'Vớ cotton dệt kim', 'Không đáp ứng điều kiện bộ bán lẻ'],
          reasoning: 'Xét từng mặt hàng theo cấu tạo và chất liệu.', source_chunk_ids: ['rule'],
          items: [{ name: 'Cà vạt', code: '62152090', source_chunk_ids: ['tie'] }, { name: 'Vớ', code: '61159500', source_chunk_ids: ['sock'] }] }] },
    });
    const result = await new ClassificationService(db, hs, auth).search('Bộ quà tặng gồm caravat và vớ', { ip: 'gift-separate' } as any);
    expect(result.status).toBe('CONDITIONAL');
    const saved = create.mock.calls[0][0].data;
    expect(saved.normalizedProduct.provisional_code).toBeUndefined();
    expect(saved.normalizedProduct.provisional_codes).toEqual(['62152090', '61159500']);
    expect(saved.legalAnalysis.decision_questions[0].source_chunk_ids).toEqual(['rule']);
    expect(saved.legalAnalysis.hypotheses[0].items[1].tariff_rates).toEqual(tariffRatesFor('61159500'));
    expect(saved.legalAnalysis.summary).not.toMatch(/chưa đủ/i);
    expect(saved.legalAnalysis.conclusion).toContain('61159500');
    expect(saved.legalAnalysis.tariff_rates).toBeNull();
  });
});
