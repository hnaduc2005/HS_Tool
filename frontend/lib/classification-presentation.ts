import type { Hypothesis, LegalAnalysis, Search, TariffRates } from './api';

export function formatHsCode(code: string) {
  const digits = code.replace(/\D/g, '');
  return digits.length === 8 ? `${digits.slice(0, 4)}.${digits.slice(4, 6)}.${digits.slice(6)}` : code;
}

export function displayRate(raw: string | null | undefined) {
  if (!raw) return 'Chưa có dữ liệu';
  if (raw === '8/10') return '8% hoặc 10%';
  if (/^0\s*\(-ID,\s*MM\)$/i.test(raw)) return '0% (trừ Indonesia, Myanmar)';
  if (/^\d+(?:[.,]\d+)?$/.test(raw)) return `${raw}%`;
  return raw.replace(/^(\d+)(?=\s|$)/, '$1%');
}

export function tariffFor(code: string, tariff?: TariffRates | null) {
  return tariff?.code === code ? tariff : null;
}

const attributeLabels: Record<string, string> = {
  material: 'Chất liệu', construction: 'Cấu tạo', drive: 'Cách vận hành', power: 'Công suất',
  phase: 'Số pha', diameter: 'Đường kính và vị trí đo', use: 'Công dụng', form: 'Dạng hàng',
  width: 'Khổ giấy', 'dimensions.length': 'Chiều còn lại của tờ giấy',
  'tie.material': 'Chất liệu cà vạt', 'socks.material': 'Chất liệu vớ',
  'tie.construction': 'Cách dệt cà vạt', 'socks.construction': 'Cách dệt vớ',
  'composition.balance': 'Phần thành phần chưa khai', 'packaging.retail': 'Đóng gói bán lẻ',
  shared_activity: 'Mục đích sử dụng chung của bộ', essential_character: 'Món tạo đặc tính chính của bộ',
  conversion_mode: 'Kiểu biến đổi điện', 'charger.status': 'Phân biệt với máy nạp pin', 'coating.form': 'Dạng lớp phủ',
  'coating.thickness_ratio': 'Tỷ lệ độ dày lớp phủ', 'adhesive.status': 'Đặc tính keo / tự dính',
  bleaching: 'Tình trạng tẩy trắng', grammage: 'Định lượng', 'grammage.unit': 'Đơn vị định lượng',
};

export function missingLabels(result: Search) {
  const attributes = result.legalAnalysis?.product_understanding?.missing_attributes;
  return [...new Set((attributes?.length ? attributes : result.missingInformation || [])
    .map(attribute => attributeLabels[attribute] || attribute))];
}

export function scenarioName(analysis: LegalAnalysis | undefined, hypothesis: Hypothesis, index: number) {
  const proposals = analysis?.declaration_information?.proposals || [];
  // A code can appear in several scenarios; match its conditions as well.
  const sameScenario = (proposal: typeof proposals[number]) => proposal.code === hypothesis.code && proposal.label === hypothesis.label;
  return proposals[index] && sameScenario(proposals[index]) ? proposals[index] : proposals.find(sameScenario);
}

export function classificationView(result: Search) {
  const primary = result.results[0];
  const completed = result.status === 'COMPLETED' && /^\d{8}$/.test(primary?.hsCode || '')
    && !result.legalAnalysis?.hypotheses?.length;
  const hypotheses = completed ? [] : (result.legalAnalysis?.hypotheses || []).filter(hypothesis =>
    /^\d{8}$/.test(hypothesis.code) && hypothesis.assumptions?.length && hypothesis.reasoning
    && (hypothesis.classification_mode !== 'separate' || (hypothesis.items && hypothesis.items.length >= 2
      && hypothesis.code === hypothesis.items[0].code && hypothesis.items.every(item => /^\d{8}$/.test(item.code)))));
  return { completed, hypotheses, primary, code: completed ? primary.hsCode : hypotheses[0]?.code || '',
    separate: hypotheses[0]?.classification_mode === 'separate',
    oldShortResult: !!primary && !/^\d{8}$/.test(primary.hsCode) };
}
