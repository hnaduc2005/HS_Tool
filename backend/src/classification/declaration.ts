import { BadRequestException } from '@nestjs/common';

export type DeclarationInput = {
  vietnamese_name?: string; composition_material?: string; use_technical?: string;
  model_code?: string; brand_origin?: string; condition?: 'new' | 'used';
  specialized_document_name?: string;
};
export const declarationFields = {
  vietnamese_name: 'Tên tiếng Việt', composition_material: 'Thành phần / Chất liệu',
  use_technical: 'Công dụng / Thông số kỹ thuật', model_code: 'Model / Code',
  brand_origin: 'Nhãn hiệu / Xuất xứ', condition: 'Tình trạng',
} as const;
type Field = keyof typeof declarationFields;
type Understanding = { product_name?: string; facts?: Array<{ attribute: string; value: string; basis: string; product_quote: string }> };
type DeclarationHypothesis = { code: string; label: string; assumptions: string[];
  assumed_attributes?: Array<{ attribute: string; value: string }>; classification_mode?: string;
  items?: Array<{ name: string; code: string }> };
export type DeclarationProposal = { code: string; label: string; name: string; assumptions: string[];
  classification_mode: 'single' | 'separate'; items: Array<{ name: string; code: string }> };
export type DeclarationInformation = {
  original_description: string;
  input: DeclarationInput; fields: Record<Field, string>; draft_name: string;
  missing_fields: Array<{ key: Field; label: string }>; warnings: string[];
  proposals: DeclarationProposal[];
  specialized_document_name: string;
  specialized_check: 'not_provided' | 'matches' | 'mismatch' | 'incomplete';
};

export function declarationDescription(description: string, declaration: DeclarationInput = {}) {
  const original = description.trim();
  if (!original && !declaration.vietnamese_name?.trim()) {
    throw new BadRequestException('Nhập mô tả sản phẩm hoặc tên hàng tiếng Việt.');
  }
  const details = Object.entries(declarationFields).flatMap(([key, label]) => {
    const value = declaration[key as Field]?.trim();
    const fact = key === 'condition' ? value === 'new' ? 'mới 100%' : 'đã qua sử dụng' : value;
    return value && fact && !comparisonName(original).includes(comparisonName(fact)) ? [`${label}: ${fact}`] : [];
  });
  const text = [original, ...details].filter(Boolean).join('\n');
  if (text.length < 2 || text.length > 2000) {
    throw new BadRequestException('Mô tả và thông tin khai báo cần có tổng độ dài từ 2 đến 2.000 ký tự. Vui lòng rút gọn nhưng giữ các thông số cần thiết.');
  }
  return text;
}

function comparisonName(value: string) {
  return value.normalize('NFC').toLocaleLowerCase('vi-VN').replace(/[\s,.;:]+/g, ' ').trim();
}

function uniqueParts(parts: string[]) {
  return parts.filter((part, index) => part && !parts.slice(0, index).some(previous => comparisonName(previous) === comparisonName(part)));
}

function automaticName(description: string) {
  const first = description.split(/\b(?:model|power|machine brand|brand|voltage)\s*[:=]|mẫu máy\s*[:=]/i)[0]
    .split(/[,;\n]/).filter(Boolean).join(' ').trim();
  const translations: Array<[RegExp, string]> = [
    [/high efficiency permanent magnet synchronous servo motor/i, 'Động cơ servo đồng bộ nam châm vĩnh cửu hiệu suất cao'],
    [/(?:permanent magnet\s+)?synchronous servo motor/i, 'Động cơ servo đồng bộ nam châm vĩnh cửu'],
    [/computerized crochet machine/i, 'Máy dệt móc điều khiển bằng máy tính'],
    [/crochet machine/i, 'Máy dệt móc'], [/pneumatic valve/i, 'Van khí nén'],
    [/\binverter\b/i, 'Biến tần'], [/plastic toy/i, 'Đồ chơi bằng nhựa'],
  ];
  return translations.reduce((name, [expression, replacement]) => name.replace(expression, replacement), first).slice(0, 300);
}

function declarationName(fields: Record<Field, string>, extra: string[] = []) {
  // Missing fields are displayed separately; they must not replace a readable
  // proposal with six placeholders or prevent classification under assumptions.
  const material = fields.composition_material;
  const namedMaterial = material && !/[;,]/.test(material) && new RegExp(`(?:^|[^\\p{L}\\p{N}])${comparisonName(material).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:$|[^\\p{L}\\p{N}])`, 'u').test(comparisonName(fields.vietnamese_name));
  return uniqueParts([fields.vietnamese_name, namedMaterial ? '' : material, fields.use_technical, ...extra,
    fields.model_code ? `Model: ${fields.model_code}` : '', fields.brand_origin, fields.condition])
    .map(part => part.trim().replace(/[,.]+$/, '')).filter(Boolean).join(', ') + '.';
}

export function declarationInformation(description: string, input: DeclarationInput = {}, understanding?: Understanding,
  hypotheses: DeclarationHypothesis[] = []): DeclarationInformation {
  const clean = Object.fromEntries(Object.entries(input).filter(([, value]) => typeof value === 'string' && value.trim())
    .map(([key, value]) => [key, value!.trim()])) as DeclarationInput;
  const knownValue = (value?: string) => value && !/^(?:chưa (?:khai|rõ|xác định|biết)|không rõ|unknown|unspecified|not specified|n\/?a)$/i.test(value.trim()) ? value : '';
  const facts = (understanding?.facts || []).filter(f => f.product_quote
    && comparisonName(description).includes(comparisonName(f.product_quote)));
  const technicalLabels: Record<string, string> = { power: 'Công suất', voltage: 'Điện áp', diameter: 'Đường kính', dimensions: 'Kích thước', width: 'Khổ', 'grammage.declared': 'Quy cách' };
  const labelled = (attribute: string, value: string) => technicalLabels[attribute] && !comparisonName(value).includes(comparisonName(technicalLabels[attribute]))
    ? `${technicalLabels[attribute]} ${value}` : value;
  const stated = (...attributes: string[]) => uniqueParts(facts.filter(f => attributes.includes(f.attribute)
    && (f.basis === 'declared' || f.attribute === 'function')).map(f => knownValue(f.value) ? labelled(f.attribute, f.value) : '')).join('; ');
  const modelMatch = description.match(/(?:\bmodel|mẫu máy|mã sản phẩm|product code)\s*[:=]\s*([^\n,;]+)/i);
  const modelText = description.replace(/[ \t]+\d+(?:[.,]\d+)?[ \t]+(?:sets?|pcs|pieces?|units?)[ \t]+\d[\d,.]*[ \t]+\d[\d,.]*[ \t]*(?=\r?\n|$)/gi, '');
  const model = modelText.match(/(?:\bmodel|mẫu máy|mã sản phẩm|product code)\s*[:=]\s*([^\n,;]+)/i)?.[1]?.trim() || '';
  const brandMatches = [...description.matchAll(/(?:\b(?:machine )?brand|nhãn hiệu|thương hiệu|hãng|(?:^|[\s,;])hiệu)\s*(?:[:=]\s*|\s+)([^\n,;]+)/gi)];
  const brand = brandMatches.find(match => !/^suất\b/i.test(match[1])
    && !/(?:không|no|without)\s*$/i.test(description.slice(Math.max(0, match.index! - 15), match.index)))?.[1]?.trim() || '';
  const absentBrand = /không\s*(?:có\s*)?(?:nhãn hiệu|thương hiệu)|\b(?:unbranded|no brand|without brand)\b/i.test(description);
  const origin = description.match(/(?:xuất xứ|\borigin\b|\bmade in\b)\s*[:=]?\s*([^\n,;]+)/i)?.[1]?.trim() || '';
  const withoutModel = modelMatch ? description.replace(modelMatch[0], '') : description;
  const conditionText = withoutModel.split(/[\n,;]/).filter(part => !/^\s*(?:model(?:\/code)?|mẫu máy|mã sản phẩm|product code)\s*[:=]/i.test(part)).join('\n');
  const newGoods = [...conditionText.matchAll(/(?:(không(?: phải)?|not)\s+)?(mới\s*100\s*%|mới\s*hoàn\s*toàn|brand[ -]new|\bnew\s*100\s*%)/gi)].some(match => !match[1]);
  const usedGoods = [...conditionText.matchAll(/(?:(chưa|không(?: phải)?|not)\s+)?(đã\s*qua\s*sử\s*dụng|second[ -]hand|condition\s*[:=]\s*used)/gi)].some(match => !match[1]);
  const specificationText = conditionText.replace(/\b(?:model|product code)\s*[:=][^\n]*/gi, '');
  const specifications: string[] = [];
  const technical = stated('use', 'function', 'power', 'voltage', 'phase', 'diameter', 'dimensions', 'width', 'grammage', 'grammage.declared');
  const measurements: Array<[RegExp, string]> = [
    [/\b\d+(?:[.,]\d+)?\s*(?:kW|W)\b/gi, 'Công suất'], [/\b\d+(?:[.,]\d+)?\s*(?:kV|V)\b/gi, 'Điện áp'],
    [/\b\d+(?:[.,]\d+)?\s*Hz\b/gi, 'Tần số'], [/\b\d+(?:[.,]\d+)?\s*(?:rpm|vòng\/phút)\b/gi, 'Tốc độ'],
    [/\b\d+(?:[.,]\d+)?\s*(?:bar|MPa|kPa)\b/gi, 'Áp suất'],
  ];
  for (const [expression, label] of measurements) {
    for (const match of specificationText.matchAll(expression)) {
      if (!/(?:không|not)\s*(?:phải\s*)?$/i.test(specificationText.slice(Math.max(0, match.index! - 15), match.index))
        && !comparisonName(technical).replace(/\s+/g, '').includes(comparisonName(match[0]).replace(/\s+/g, ''))) specifications.push(`${label} ${match[0]}`);
    }
  }
  if (/\bcomputerized\b/i.test(description)) specifications.push('Điều khiển bằng máy tính');
  const phase = [...specificationText.matchAll(/(?:\b(?:single|three|multi)[ -]phase\b|\b(?:một|ba|đa|1|3)\s*pha\b)/gi)]
    .find(match => !/(?:không|not)\s*(?:phải\s*)?$/i.test(specificationText.slice(Math.max(0, match.index! - 15), match.index)))?.[0];
  if (phase) specifications.push(phase.replace(/single[ -]phase/i, 'một pha').replace(/three[ -]phase/i, 'ba pha').replace(/multi[ -]phase/i, 'đa pha'));
  const dimensions = specificationText.match(/\b\d+(?:[.,]\d+)?\s*[x×*]\s*\d+(?:[.,]\d+)?(?:\s*[x×*]\s*\d+(?:[.,]\d+)?)?\s*mm\b/i)?.[0];
  if (dimensions) specifications.push(`Kích thước ${dimensions}`);
  const fields: Record<Field, string> = {
    vietnamese_name: knownValue(clean.vietnamese_name) || knownValue(understanding?.product_name) || automaticName(description),
    composition_material: knownValue(clean.composition_material) || stated('material', 'material.base_paper', 'coating.material', 'composition.declared', 'composition', 'tie.material', 'socks.material'),
    use_technical: knownValue(clean.use_technical) || uniqueParts([technical, ...specifications]).join('; '),
    model_code: knownValue(clean.model_code) || knownValue(model),
    brand_origin: knownValue(clean.brand_origin) || [knownValue(brand) ? `Nhãn hiệu: ${brand}` : absentBrand ? 'Không nhãn hiệu' : '', knownValue(origin) ? `Xuất xứ: ${origin}` : ''].filter(Boolean).join('; '),
    condition: clean.condition ? clean.condition === 'new' ? 'mới 100%' : 'đã qua sử dụng'
      : newGoods !== usedGoods ? newGoods ? 'mới 100%' : 'đã qua sử dụng' : '',
  };
  const missing = (Object.keys(declarationFields) as Field[]).filter(key => !fields[key]).map(key => ({ key, label: declarationFields[key] }));
  const warnings: string[] = [];
  if (missing.some(field => field.key === 'condition')) warnings.push('Chưa khai tình trạng: chọn mới 100% hoặc đã qua sử dụng.');
  if (newGoods && usedGoods) warnings.push('Mô tả có cả tình trạng mới và đã qua sử dụng; cần kiểm tra lại.');
  if (/^(?:phụ tùng xe máy|linh kiện máy tính|mỹ phẩm|nông sản)[\s.!…]*$/i.test(fields.vietnamese_name || description.trim())) {
    warnings.push('Tên hàng quá chung chung; cần nêu loại sản phẩm cụ thể, chất liệu, công dụng và đặc điểm để đối chiếu mã HS.');
  }
  if (!/[À-ỹđĐ]/.test(fields.vietnamese_name) && /\b(?:plastic|toy|machine|motor|inverter|valve|parts|cosmetics)\b/i.test(fields.vietnamese_name || description)) {
    warnings.push('Cần dịch tên hàng sang tiếng Việt và mô tả đặc điểm; không chỉ sao chép tên tiếng Anh trên Invoice.');
  }
  const draft = declarationName(fields);
  const proposals: DeclarationProposal[] = hypotheses.map(hypothesis => {
    const extra = uniqueParts((hypothesis.assumed_attributes || []).filter(attribute =>
      /(?:^|\.)(?:material|composition|balance|power|power_range|phase|voltage|current_type|use|function|drive|construction|conversion_mode)$/.test(attribute.attribute))
      .map(attribute => labelled(attribute.attribute, attribute.value.trim())).filter(value => value && !comparisonName(draft).includes(comparisonName(value))));
    const separate = hypothesis.classification_mode === 'separate';
    return { code: hypothesis.code, label: hypothesis.label, name: declarationName(fields, extra),
      assumptions: hypothesis.assumptions, classification_mode: separate ? 'separate' : 'single',
      items: separate ? (hypothesis.items || []).map(item => ({ name: item.name, code: item.code })) : [] };
  });
  const specialized = clean.specialized_document_name || '';
  const check = !specialized ? 'not_provided' : missing.length ? 'incomplete'
    : comparisonName(draft) === comparisonName(specialized) ? 'matches' : 'mismatch';
  if (check === 'mismatch') warnings.push('Tên hàng gợi ý chưa khớp tên trên chứng từ chuyên ngành; đối chiếu và chỉnh lại trước khi khai báo.');
  return { original_description: description, input: clean, fields, draft_name: draft, missing_fields: missing, warnings, proposals,
    specialized_document_name: specialized, specialized_check: check };
}
