import { declarationDescription, declarationInformation, type DeclarationInput } from './declaration';

const pump: DeclarationInput = {
  vietnamese_name: 'Máy bơm nước ly tâm', composition_material: 'Thân bằng gang',
  use_technical: 'dùng trong công nghiệp, công suất 5kW, điện áp 380V',
  model_code: 'PU-500', brand_origin: 'hiệu Ebara, xuất xứ Nhật Bản', condition: 'new',
};

describe('declaration information', () => {
  it('keeps invoice quantities and monetary columns out of the model name', () => {
    const inverter = declarationInformation('INVERTER, MODEL: JK200A-055-4T 2 SET 1,245.00 2,490.00');
    expect(inverter.fields.model_code).toBe('JK200A-055-4T');
    expect(inverter.draft_name).not.toContain('1,245.00');
    const motor = declarationInformation('HIGH EFFICIENCY PERMANENT MAGNET\nSYNCHRONOUS SERVO MOTOR, MODEL:\nTVF225M-8-75-152 WT-S1700\n2 PCS 3,179.00 6,358.00');
    expect(motor.fields.model_code).toBe('TVF225M-8-75-152 WT-S1700');
    expect(motor.fields.use_technical).not.toContain('75');
  });
  it('accepts short product names without inventing missing specifications', () => {
    expect(declarationDescription('Vớ')).toBe('Vớ');
    expect(declarationDescription('Áo')).toBe('Áo');
    expect(() => declarationDescription(' ')).toThrow();
  });
  it('retains the paper coating, raw QC, use, absent brand and new condition in its automatic name', () => {
    const description = 'Giấy trang trí phủ PU, QC: 1270MM *30G~45G, dùng dán giả vân gỗ trên bề mặt ván, không nhãn hiệu, có nhãn hàng hóa, hàng mới 100%';
    const result = declarationInformation(description, {}, { product_name: 'Giấy trang trí phủ PU', facts: [
      { attribute: 'coating.material', value: 'PU', basis: 'declared', product_quote: 'phủ PU' },
      { attribute: 'width', value: '1270MM', basis: 'declared', product_quote: '1270MM' },
      { attribute: 'grammage.declared', value: '30G~45G', basis: 'declared', product_quote: '30G~45G' },
      { attribute: 'use', value: 'dùng dán giả vân gỗ trên bề mặt ván', basis: 'declared', product_quote: 'dùng dán giả vân gỗ trên bề mặt ván' },
    ] });
    for (const fact of ['PU', '1270MM', '30G~45G', 'bề mặt ván', 'Không nhãn hiệu', 'mới 100%']) expect(result.draft_name).toContain(fact);
    expect(result.draft_name).not.toContain('g/m²');
    expect(result.draft_name).not.toContain('PU, PU');
    expect(result.missing_fields.map(field => field.key)).not.toContain('brand_origin');
    expect(result.proposals).toEqual([]);
  });
  it('builds all six groups in order from declared facts', () => {
    const input = declarationDescription('', pump);
    const result = declarationInformation(input, pump);
    expect(result.draft_name).toBe('Máy bơm nước ly tâm, Thân bằng gang, dùng trong công nghiệp, công suất 5kW, điện áp 380V, Model: PU-500, hiệu Ebara, xuất xứ Nhật Bản, mới 100%.');
    expect(result.missing_fields).toEqual([]);
    expect(result.fields.condition).toBe('mới 100%');
  });

  it('keeps missing condition, model and origin out of confirmed declaration facts', () => {
    const result = declarationInformation('CROCHET MACHINE, 1.5 kW', {}, {
      product_name: 'Máy dệt móc', facts: [
        { attribute: 'power', value: '1.5 kW', basis: 'declared', product_quote: '1.5 kW' },
        { attribute: 'material', value: 'thép', basis: 'declared', product_quote: 'not present' },
        { attribute: 'material', value: 'thép', basis: 'definition', product_quote: 'CROCHET MACHINE' },
      ],
    });
    expect(result.fields.composition_material).toBe('');
    expect(result.fields.condition).toBe('');
    expect(result.fields.model_code).toBe('');
    expect(result.fields.brand_origin).toBe('');
    expect(result.draft_name).toBe('Máy dệt móc, Công suất 1.5 kW.');
    expect(result.missing_fields.some(field => field.key === 'condition')).toBe(true);
    expect(result.draft_name).not.toContain('mới 100%');
    expect(result.fields.use_technical).toBe('Công suất 1.5 kW');
  });

  it.each(['Phụ tùng xe máy', 'Linh kiện máy tính', 'Mỹ phẩm', 'Nông sản'])('flags generic article %s', name => {
    expect(declarationInformation(name, { vietnamese_name: name }).warnings.join(' ')).toContain('quá chung chung');
  });

  it('flags copied English invoice names', () => {
    expect(declarationInformation('Plastic Toy', { vietnamese_name: 'Plastic Toy' }).warnings.join(' ')).toContain('sang tiếng Việt');
  });

  it('parses explicitly labelled model and brand without guessing origin or condition', () => {
    const result = declarationInformation('COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW');
    expect(result.fields.model_code).toBe('B16 20');
    expect(result.fields.brand_origin).toBe('Nhãn hiệu: YJ');
    expect(result.fields.condition).toBe('');
  });

  it('compares specialized names with case, punctuation and PDF whitespace normalized', () => {
    const result = declarationInformation('', pump);
    const match = declarationInformation('', { ...pump, specialized_document_name: result.draft_name.toUpperCase().replace(/, /g, ';\n') });
    expect(match.specialized_check).toBe('matches');
    const mismatch = declarationInformation('', { ...pump, specialized_document_name: result.draft_name.replace('5kW', '7kW') });
    expect(mismatch.specialized_check).toBe('mismatch');
    expect(mismatch.warnings.join(' ')).toContain('chưa khớp');
  });

  it('does not claim certificate agreement when the name is incomplete', () => {
    expect(declarationInformation('Plastic Toy', { specialized_document_name: 'Plastic Toy' }).specialized_check).toBe('incomplete');
  });

  it('keeps certificate text separate from product facts sent to AI', () => {
    const input = declarationDescription('Máy bơm ly tâm', { ...pump, specialized_document_name: 'PRIVATE CERTIFICATE NAME' });
    expect(input).toContain('Tình trạng: mới 100%');
    expect(input).not.toContain('PRIVATE CERTIFICATE NAME');
  });

  it('rejects overlong combined facts without truncating ratings', () => {
    expect(() => declarationDescription('A'.repeat(1990), pump)).toThrow('2.000');
    expect(() => declarationDescription('', { condition: 'new' })).toThrow('Nhập mô tả');
  });

  it('does not infer new condition from negated or unspecified condition', () => {
    expect(declarationInformation('Máy bơm, không mới 100%').fields.condition).toBe('');
    expect(declarationInformation('Máy bơm, chưa đã qua sử dụng').fields.condition).toBe('');
    expect(declarationInformation('Máy bơm, đã qua sử dụng').fields.condition).toBe('đã qua sử dụng');
    expect(declarationInformation('Máy bơm, không phải mới 100%').fields.condition).toBe('');
    const model = declarationInformation('Original pump, MODEL: NEW100%');
    expect(model.fields.condition).toBe('');
    expect(model.fields.brand_origin).toBe('');
  });
  it('keeps unspecified fields missing while retaining the entered form for editing', () => {
    const input = { composition_material: 'chưa rõ', brand_origin: 'unknown', model_code: 'N/A' };
    const result = declarationInformation('Máy bơm không rõ vật liệu', input);
    expect(result.fields.composition_material).toBe('');
    expect(result.fields.brand_origin).toBe('');
    expect(result.fields.model_code).toBe('');
    expect(result.input).toEqual(input);
  });
  it('does not repeat recipe percentages already in the original description', () => {
    const recipe = 'Gạo 55%; tôm 11%; thịt lợn 10%; rau 14%';
    const text = declarationDescription(`Cơm chiên: ${recipe}`, { composition_material: recipe, condition: 'new' });
    expect(text.match(/55%/g)).toHaveLength(1);
    expect(text).toContain('Tình trạng: mới 100%');
  });

  it('automatically proposes a readable name and stated specifications without form input', () => {
    const result = declarationInformation('COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW');
    expect(result.draft_name).toBe('Máy dệt móc điều khiển bằng máy tính, Công suất 1.5KW; Điều khiển bằng máy tính, Model: B16 20, Nhãn hiệu: YJ.');
    expect(result.draft_name).not.toContain('chưa khai');
    expect(result.fields.condition).toBe('');
  });

  it('extracts the brand and voltage from the supplied Vietnamese example without inventing origin', () => {
    const result = declarationInformation('Máy bơm nước ly tâm dùng trong công nghiệp, công suất 5kW, điện áp 380V, Model: PU-500, hiệu Ebara, mới 100%.', {}, { product_name: 'Máy bơm nước ly tâm' });
    expect(result.fields.brand_origin).toBe('Nhãn hiệu: Ebara');
    expect(result.fields.model_code).toBe('PU-500');
    expect(result.fields.use_technical).toContain('5kW');
    expect(result.fields.use_technical).toContain('380V');
    expect(result.fields.condition).toBe('mới 100%');
  });

  it('does not mistake efficiency or negated branding for a brand', () => {
    expect(declarationInformation('Động cơ hiệu suất cao, không nhãn hiệu, mới 100%').fields.brand_origin).toBe('Không nhãn hiệu');
    expect(declarationInformation('Máy bơm, MODEL: 45kW').fields.use_technical).toBe('');
    expect(declarationInformation('Máy bơm\nMODEL:\n45kW').fields.use_technical).toBe('');
    expect(declarationInformation('Máy bơm\nMODEL:\nNEW100%').fields.condition).toBe('');
    expect(declarationInformation('Máy bơm, not single-phase').fields.use_technical).toBe('');
  });

  it('keeps declared specifications in each conditional name and labels hypothetical values separately', () => {
    const result = declarationInformation('SYNCHRONOUS SERVO MOTOR, MODEL: TVF225M-8-45-152', {},
      { product_name: 'Động cơ servo đồng bộ' }, [{ code: '85015229', label: 'Công suất trên 1 đến 37,5 kW',
        assumptions: ['Công suất trên 1 đến 37,5 kW, điện xoay chiều đa pha'],
        assumed_attributes: [{ attribute: 'power', value: 'Công suất trên 1 đến 37,5 kW' }, { attribute: 'phase', value: 'đa pha' }] }]);
    expect(result.draft_name).toBe('Động cơ servo đồng bộ, Model: TVF225M-8-45-152.');
    expect(result.fields.use_technical).toBe('');
    expect(result.proposals[0].name).toContain('Công suất trên 1 đến 37,5 kW');
    expect(result.proposals[0].name).toContain('Model: TVF225M-8-45-152');
    expect(result.proposals[0].assumptions).toHaveLength(1);
    expect(result.proposals[0].name).not.toContain('mới 100%');
  });
});
