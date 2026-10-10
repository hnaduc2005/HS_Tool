const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const localRequire = createRequire(path.join(root, 'package.json'));
const ts = localRequire('typescript');
const React = localRequire('react');
const { renderToStaticMarkup } = localRequire('react-dom/server');
const cache = new Map();
function load(relative) {
  const filename = path.join(root, relative);
  if (cache.has(filename)) return cache.get(filename);
  const module = { exports: {} };
  const requireAlias = name => {
    if (!name.startsWith('@/')) return localRequire(name);
    const base = name.slice(2);
    const extension = ['.ts', '.tsx'].find(ext => fs.existsSync(path.join(root, base + ext)));
    assert(extension, 'Unknown module: ' + name);
    return load(base + extension);
  };
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  vm.runInThisContext('(function(require,module,exports){' + compiled + '\n})', { filename })(requireAlias, module, module.exports);
  cache.set(filename, module.exports);
  return module.exports;
}
const { ClassificationAnswer } = load('components/classification-answer.tsx');
const { ClassificationTariff } = load('components/classification-tariff.tsx');
const { ClassificationBatch } = load('components/classification-batch.tsx');
const { ProductListEditor } = load('components/product-list-editor.tsx');
const { runClassificationBatch, batchError, hasNumberedRows, prepareDraftItems } = load('lib/classification-batch.ts');
const tariff = (code, mfn) => ({ code, mfn, normal: '18', vat: '8/10', atiga: '0', acfta: '0', akfta: null, source: 'Dữ liệu thử giao diện' });
const hypothesis = (label, assumptions, rate = '12') => ({ code: '85044090', label, classification_mode: 'single',
  assumptions, assumed_attributes: [{ attribute: 'conversion_mode', value: assumptions[0] }],
  reasoning: 'Đối chiếu chức năng biến đổi điện tĩnh và nhánh quốc gia tương ứng.', source_chunk_ids: ['rule'], tariff_rates: tariff('85044090', rate) });
function result() {
  return { id: 'fixture', productDescription: 'Giấy trang trí phủ PU, QC: 1270MM *30G~45G, mới 100%',
    normalizedProduct: { product_name: 'Giấy trang trí phủ PU' }, status: 'COMPLETED', missingInformation: [],
    results: [{ id: 'primary', hsCode: '48119099', reasoning: 'Giấy trang trí bề mặt theo dữ kiện đã khai.', sources: [] }],
    legalAnalysis: { summary: 'Giấy trang trí dán trên bề mặt ván, theo nhánh giấy khác.',
      product_understanding: { product_name: 'Giấy trang trí phủ PU', meaning: 'Hàng nhập là giấy, ván là bề mặt sử dụng.', facts: [], missing_attributes: [], definition_source_ids: ['rule'] },
      legal_steps: [{ rule: 'Quy tắc 1', application: 'Đối chiếu tên hàng và chú giải.', source_chunk_ids: ['rule'] }],
      hypotheses: [], alternatives: [{ code: '48115999', reason: 'Không chọn giấy ghép màng plastic khi mô tả xác định giấy trang trí bề mặt.', source_chunk_ids: ['rule'] }],
      references: [{ chunk_id: 'rule', title: 'Nguồn thử', source: 'Tài liệu thử', excerpt: 'Nội dung thử', page: 1 }],
      tariff_rates: tariff('48119099', '12'), suggested_name: 'Giấy trang trí phủ PU, khổ 1270MM, QC: 30G~45G, mới 100%.',
    } };
}
const render = data => renderToStaticMarkup(React.createElement(ClassificationAnswer, { result: data }));
const conditional = hypotheses => {
  const data = result();
  data.status = 'CONDITIONAL'; data.results = []; data.productDescription = 'Máy biến đổi tĩnh điện, công suất 7kW';
  data.legalAnalysis.hypotheses = hypotheses;
  data.legalAnalysis.product_understanding.missing_attributes = ['conversion_mode'];
  data.legalAnalysis.product_understanding.facts = [{ attribute: 'power', value: 'Công suất 7kW', basis: 'declared', source_chunk_ids: [] }];
  data.legalAnalysis.tariff_rates = tariff('85044090', '97'); // Must not overwrite each scenario's rates.
  return data;
};

test('complete result puts the code first, provides name/reason/tax/comparisons and no assumption cards', () => {
  const html = render(result());
  assert(html.indexOf('4811.90.99') < html.indexOf('Tên hàng đề xuất'));
  for (const text of ['1270MM', '30G~45G', 'Vì sao đề xuất', 'Thuế suất', 'NK ưu đãi', 'GTGT', 'Mã HS dễ nhầm', '4811.59.99', '12%']) assert(html.includes(text));
  assert(!html.includes('Giả định phần còn thiếu'));
  assert(!html.includes('Phương án 1:'));
  assert(!html.includes('Chào Sếp'));
});

test('one conditional scenario has its own taxes and preserves supplied power', () => {
  const html = render(conditional([hypothesis('Biến tần', ['Dùng điều chỉnh tần số dòng điện'])]));
  for (const text of ['Phương án 1:', 'Giả định phần còn thiếu', 'Vì sao chọn mã này?', 'Tên hàng theo phương án này', 'Thuế suất', 'Công suất 7kW', '12%']) assert(html.includes(text));
  assert(!html.includes('97%'));
  assert(!html.includes('conversion_mode'));
  assert(!html.includes('<table'));
});

test('same-code scenarios retain their own declaration names and rates', () => {
  const data = conditional([hypothesis('Biến tần', ['Điều chỉnh tần số'], '12'), hypothesis('Bộ biến đổi DC-DC', ['Biến đổi điện một chiều'], '15')]);
  data.legalAnalysis.declaration_information = { draft_name: 'Máy biến đổi tĩnh điện, công suất 7kW.',
    proposals: [
      { code: '85044090', label: 'Bộ biến đổi DC-DC', name: 'Bộ biến đổi DC-DC, công suất 7kW.' },
      { code: '85044090', label: 'Biến tần', name: 'Biến tần, công suất 7kW.' },
    ], fields: {}, missing_fields: [], warnings: [], specialized_check: 'not_provided' };
  const html = render(data);
  const first = html.slice(html.indexOf('aria-label="Phương án 1"'), html.indexOf('aria-label="Phương án 2"'));
  const second = html.slice(html.indexOf('aria-label="Phương án 2"'));
  assert(first.includes('Biến tần, công suất 7kW.'));
  assert(!first.includes('Bộ biến đổi DC-DC, công suất 7kW.'));
  assert(first.includes('12%'));
  assert(second.includes('Bộ biến đổi DC-DC, công suất 7kW.'));
  assert(second.includes('15%'));
});

test('separate classification shows each article and its tax without a combined whole-set code', () => {
  const data = conditional([{ ...hypothesis('Không đáp ứng bộ bán lẻ', ['Phân loại riêng cà vạt và vớ']), code: '62152090', classification_mode: 'separate',
    items: [{ name: 'Cà vạt polyester', code: '62152090', source_chunk_ids: ['rule'], tariff_rates: tariff('62152090', '17') },
      { name: 'Vớ cotton', code: '61159500', source_chunk_ids: ['rule'], tariff_rates: tariff('61159500', '20') }] }]);
  const html = render(data);
  for (const text of ['Phân loại riêng từng mặt hàng', 'Cà vạt polyester', 'Vớ cotton', '6215.20.90', '6115.95.00', '17%', '20%']) assert(html.includes(text));
  assert(!html.includes('97%'));
});

test('a mismatched tariff is never displayed as the selected code tax', () => {
  const html = renderToStaticMarkup(React.createElement(ClassificationTariff, { code: '48119099', tariff: tariff('85044090', '97') }));
  assert(!html.includes('97%'));
  assert(html.includes('Chưa có dữ liệu thuế'));
});

test('a provisional code without verified proposals is not promoted to the main recommendation', () => {
  const data = result(); data.status = 'INSUFFICIENT_EVIDENCE'; data.results = [];
  data.normalizedProduct.provisional_code = '85044090';
  const html = render(data);
  assert(html.includes('Chưa có phương án mã hợp lệ'));
  assert(!html.includes('8504.40.90'));
});

test('a stored completed status with physical assumptions is presented conditionally', () => {
  const data = result(); data.legalAnalysis.hypotheses = [hypothesis('Biến tần', ['Điều chỉnh tần số'])];
  const html = render(data);
  assert(html.includes('Mã HS theo từng giả định'));
  assert(html.includes('Giả định phần còn thiếu'));
  assert(!html.includes('Vì sao đề xuất 4811.90.99'));
});

test('batch cards show separate codes, default collapses and unique citation links', () => {
  const first = result(); first.id = 'paper';
  const second = result(); second.id = 'machine'; second.results[0].hsCode = '84479010';
  second.legalAnalysis.tariff_rates = tariff('84479010', '7');
  const items = [first, second].map((record, index) => ({ key: `product-${index}`, description: record.productDescription,
    declaration: {}, state: 'done', result: record }));
  const html = renderToStaticMarkup(React.createElement(ClassificationBatch, { items, busy: false, onRetry() {} }));
  for (const text of ['Kết quả 2 mặt hàng', '4811.90.99', '8447.90.10', 'Mở tất cả', 'Thu gọn tất cả']) assert(html.includes(text));
  assert(html.includes('aria-controls="batch-body-product-0"'));
  assert(html.includes('aria-expanded="true"'));
  assert(html.includes('aria-expanded="false"'));
  assert(html.includes('id="batch-body-product-1" hidden=""'));
  assert(html.includes('href="#legal-source-paper-rule"'));
  assert(html.includes('href="#legal-source-machine-rule"'));
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length, 'Duplicate DOM ids across products');
});

test('batch continues after one upstream failure and keeps each product declaration separate', async () => {
  const items = [0, 1, 2].map(index => ({ key: `item-${index}`, description: `Product model ${index}`, declaration: { model_code: `${index}` }, state: 'waiting' }));
  const updates = []; const seen = [];
  await runClassificationBatch(items, async item => {
    seen.push([item.description, item.declaration.model_code]);
    if (item.key === 'item-1') throw new Error('Quota unavailable');
    return { ...result(), id: item.key };
  }, (key, patch) => updates.push({ key, ...patch }));
  assert.deepEqual(seen, items.map(item => [item.description, item.declaration.model_code]));
  assert.deepEqual(updates.filter(update => update.state !== 'loading').map(update => [update.key, update.state]),
    [['item-0', 'done'], ['item-1', 'error'], ['item-2', 'done']]);
  assert.equal(updates.find(update => update.key === 'item-1' && update.state === 'error').error, 'Quota unavailable');
});

test('list editor scopes form ids and rejects oversized products before submission', () => {
  const items = ['first', 'second'].map(key => ({ key, description: 'INVERTER MODEL ' + key, declaration: {}, state: 'waiting' }));
  const html = renderToStaticMarkup(React.createElement(ProductListEditor, { items, onChange() {} }));
  assert(html.includes('id="first-decl-model"') && html.includes('id="second-decl-model"'));
  assert(html.includes('for="first-decl-model"') && html.includes('for="second-decl-model"'));
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(batchError(items), '');
  assert.equal(batchError([{ ...items[0], description: 'Vớ' }]), '');
  assert(batchError([{ ...items[0], description: 'a'.repeat(2001) }]).includes('2.000'));
  assert(batchError(Array(11).fill(items[0])).includes('10'));
});

test('batch summary agrees with the conditional body for a stale completed record', () => {
  const record = result(); record.legalAnalysis.hypotheses = [hypothesis('Biến tần', ['Điều chỉnh tần số'])];
  const html = renderToStaticMarkup(React.createElement(ClassificationBatch, { items: [
    { key: 'stale', description: record.productDescription, declaration: {}, state: 'done', result: record },
  ], busy: false, onRetry() {} }));
  const header = html.slice(html.indexOf('<h3>'), html.indexOf('id="batch-body-stale"'));
  assert(header.includes('8504.40.90') && header.includes('Theo giả định'));
  assert(!header.includes('4811.90.99') && !header.includes('Đủ thông tin'));
});

test('a ten-row invoice pasted into one editor card expands before classification', async () => {
  const description = fs.readFileSync(path.resolve(root, '../ai-service/tests/fixtures/invoice-ten-products.txt'), 'utf8').trim();
  const source = { key: 'pasted', description, declaration: {}, state: 'waiting' };
  assert(hasNumberedRows(description));
  assert(!hasNumberedRows('CROCHET MACHINE\nPOWER: 1.5KW\nMODEL: B16 20'));
  const rows = description.split(/\n\s*\n/).map(text => ({ description: text.replace(/^\d+\.\s+/, '') }));
  const prepared = await prepareDraftItems([source], async actual => {
    assert.equal(actual, description); return { items: rows, needs_review: false, message: '' };
  });
  assert.equal(prepared.items.length, 10);
  assert(!prepared.needsReview);
  assert.equal(new Set(prepared.items.map(item => item.key)).size, 10);
  const sent = [];
  await runClassificationBatch(prepared.items, async item => { sent.push(item.description); return result(); }, () => {});
  assert.deepEqual(sent, rows.map(row => row.description));
  assert.equal(sent.filter(row => row.startsWith('INVERTER')).length, 4);
  assert.equal(sent.filter(row => row.includes('SERVO MOTOR')).length, 6);
});

test('uncertain segmentation is not presented as a confirmed one-product list', () => {
  const html = renderToStaticMarkup(React.createElement(ProductListEditor, {
    items: [{ key: 'review', description: 'Unresolved list of multiple products', declaration: {}, state: 'waiting' }],
    needsReview: true, onChange() {},
  }));
  assert(html.includes('Nội dung cần kiểm tra cách tách'));
  assert(!html.includes('Danh sách 1 mặt hàng'));
});

test('splitting an editor card preserves unassigned declaration facts for review', async () => {
  const item = { key: 'facts', description: '1. INVERTER MODEL A\n2. MOTOR MODEL B', declaration: { model_code: 'A' }, state: 'waiting' };
  const prepared = await prepareDraftItems([item], async () => ({ items: [{ description: 'INVERTER MODEL A' }, { description: 'MOTOR MODEL B' }], needs_review: false, message: '' }));
  assert(prepared.needsReview && prepared.message.includes('2 mặt hàng'));
  assert.deepEqual(prepared.items, [item]);
});
