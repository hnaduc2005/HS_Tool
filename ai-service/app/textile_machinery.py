"""Use the declared/defined mechanism; vary only genuinely missing attributes."""
import re
from .electrical_classification import positive_description
from .legal_text import contains_phrase


EVIDENCE = {
    'crochet': ['máy dệt móc'],
    'flat': ['Máy dệt kim phẳng bao gồm'],
    'stitch': ['(B) MÁY KHÂU ĐÍNH'],
    'circular': ['(1) Máy dệt kim tròn'],
    'embroidery': ['(5) Máy thêu'],
    'braiding': ['(7) Máy sản xuất đồ trang trí'],
    'lace': ['(3) Máy sản xuất tuyn hình thoi'],
    'tufting': ['(9) Máy tết'],
}


def textile_function(description: str) -> str | None:
    text = positive_description(description)
    if re.search(r'\b(?:parts? for|spare parts?|needles? for|controller for|motor for|control panel for)\b|phụ tùng|linh kiện|bộ phận của|kim cho|động cơ (?:cho|của)|crochet hooks?|móc đan', text, re.I):
        return None
    if not re.search(r'\bmachine\b|máy\b', text, re.I):
        return None
    # Heading 84.47 explicitly excludes ordinary sewing machines whose
    # embroidery operation is subsidiary to sewing (heading 84.52).
    if re.search(r'sewing machine|máy khâu(?!\s+đính)', text, re.I):
        return None
    patterns = [
        ('stitch', r'stitch[ -]bonding|máy khâu đính'),
        ('circular', r'circular.*knitting|dệt kim tròn'),
        ('flat', r'flat.*knitting|warp.*knitting|raschel|milanese|locknit|dệt kim phẳng|dệt kim sợi dọc'),
        ('crochet', r'crochet|máy dệt móc'),
        ('embroidery', r'embroidery|máy thêu'),
        ('braiding', r'braiding|máy (?:bện|tết dây)|máy dệt viền'),
        ('lace', r'lace[ -]making|tulle[ -]making|máy (?:sản xuất|dệt) (?:ren|tuyn)'),
        ('tufting', r'tufting|máy tạo búi'),
    ]
    return next((kind for kind, pattern in patterns if re.search(pattern, text, re.I)), None)


def drive(description: str) -> bool | None:
    # "Computerized" describes control; hand operation does not establish
    # whether the machine itself is electrically driven.
    if re.search(r'non[ -]electric|without (?:electric|motor)|không (?:hoạt động|vận hành) bằng điện', description, re.I):
        return False
    text = positive_description(description)
    if re.search(r'(?<!\w)(?:\d+(?:[.,]\d+)?)\s*(?:kW|W)\b|electrically operated|electric (?:motor|drive)|hoạt động bằng điện|chạy điện', text, re.I):
        return True
    return None


def catalog_mechanism(candidate: dict) -> str | None:
    if not str(candidate.get('code', '')).startswith('8447'):
        return None
    parts = [p.strip().lstrip('-').strip().rstrip(':').casefold() for p in candidate.get('description', '').split('→')]
    # A heading title listing all mechanisms is not a branch condition.
    if any(p == 'máy dệt kim phẳng; máy khâu đính' for p in parts):
        return 'flat_stitch'
    if any(p == 'máy dệt kim tròn' for p in parts):
        return 'circular'
    if len(parts) >= 2 and 'loại khác' in parts[:-1]:
        return 'other'
    if len(str(candidate.get('code', ''))) == 6 and parts[-1:] == ['loại khác']:
        return 'other'
    return None


def candidate_drive(candidate: dict) -> bool | None:
    leaf = candidate.get('description', '').split('→')[-1].strip().lstrip('-').strip().casefold()
    return False if leaf == 'không hoạt động bằng điện' else True if leaf == 'hoạt động bằng điện' else None


def relevant_mechanisms(description: str) -> set[str]:
    function = textile_function(description)
    if function in ('flat', 'stitch'):
        return {'flat_stitch'}
    if function == 'circular':
        return {'circular'}
    if function == 'crochet':
        return {'other'}
    return {'other'} if function else set()


def cylinder_diameter(description: str) -> float | None:
    match = re.search(r'(?:cylinder diameter|diameter of (?:the )?cylinder|đường kính trục cuốn)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(mm|cm)\b', positive_description(description), re.I)
    return float(match[1].replace(',', '.')) * (10 if match[2].lower() == 'cm' else 1) if match else None


def textile_candidates(description: str, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    mechanisms = relevant_mechanisms(description)
    if not mechanisms:
        return candidates, []
    powered, diameter = drive(description), cylinder_diameter(description)
    eligible = []
    for candidate in candidates:
        mechanism = catalog_mechanism(candidate)
        if mechanism not in mechanisms:
            continue
        candidate_powered = candidate_drive(candidate)
        if powered is not None and candidate_powered is not None and powered != candidate_powered:
            continue
        if mechanism == 'circular' and diameter is not None:
            small = 'không quá 165' in candidate['description']
            large = 'trên 165' in candidate['description']
            if (small and diameter > 165) or (large and diameter <= 165):
                continue
        eligible.append(candidate)
    return eligible, [c for c in candidates if c not in eligible]


def missing_primary_branch(description: str, candidates: list[dict]) -> bool:
    if textile_function(description) != 'crochet':
        return False
    return not any(len(c['code']) == 8 and catalog_mechanism(c) == 'other' for c in textile_candidates(description, candidates)[0])


def textile_evidence_phrases(function: str) -> list[str]:
    keys = [function, 'flat'] if function == 'crochet' else [function]
    return [phrase for key in keys for phrase in EVIDENCE.get(key, [])]


def textile_source_ids(function: str, chunks: list[dict]) -> list[str]:
    return [c['chunk_id'] for c in chunks if any(contains_phrase(c.get('content', ''), p) for p in EVIDENCE.get(function, []))]


def textile_scenarios(description: str, candidates: list[dict]) -> list[dict]:
    function = textile_function(description)
    if not function:
        return []
    powered, diameter = drive(description), cylinder_diameter(description)
    options = []
    for candidate in textile_candidates(description, candidates)[0]:
        if len(candidate['code']) != 8:
            continue
        mechanism = catalog_mechanism(candidate)
        assumptions, assumed_attributes, identified_conditions = [], [], []
        evidence_function = function
        if mechanism == 'other':
            if function == 'crochet':
                label = 'Máy dệt móc'
                identified_conditions += ['Crochet machine là máy dệt móc được mô tả tại mục (C)(7) của chú giải nhóm', 'Không đổi nghĩa đã xác định thành máy dệt kim phẳng hoặc máy khâu đính để tạo thêm phương án']
            else:
                names = {'embroidery': 'Máy thêu', 'braiding': 'Máy tết dây hoặc đồ trang trí', 'lace': 'Máy sản xuất ren hoặc tuyn', 'tufting': 'Máy tạo búi'}
                label = names[function]
                identified_conditions += ['Tên hàng đã xác định ' + label.lower() + ' theo đoạn định nghĩa tương ứng của chú giải nhóm']
            priority = 0
        elif mechanism == 'flat_stitch':
            priority = 0
            evidence_function = 'stitch' if function == 'stitch' else 'flat'
            label = 'Máy khâu đính' if function == 'stitch' else 'Máy dệt kim phẳng hoặc sợi dọc'
            identified_conditions += ['Tên hàng đã xác định ' + label.lower() + ' theo chú giải nhóm']
        else:
            text = candidate['description']
            if 'không quá 165' in text:
                small, bound = True, 'không quá 165 mm'
            elif 'trên 165' in text:
                small, bound = False, 'trên 165 mm'
            else:
                continue
            priority = 0 if small else 1
            label = 'Máy dệt kim tròn; đường kính trục cuốn ' + bound
            identified_conditions += ['Tên hàng đã xác định máy dệt kim tròn theo mục (A)(1)']
            if diameter is None:
                assumptions += ['Giả định đường kính TRỤC CUỐN ' + bound + '; không sử dụng kích thước tổng thể hoặc số model làm đường kính trục cuốn']
                assumed_attributes.append({'attribute': 'diameter', 'value': bound})
        candidate_powered = candidate_drive(candidate)
        if candidate_powered is not None:
            label += ', ' + ('hoạt động bằng điện' if candidate_powered else 'không hoạt động bằng điện')
            if powered is None:
                assumptions += ['Giả định máy ' + ('hoạt động bằng điện' if candidate_powered else 'không hoạt động bằng điện')]
                assumed_attributes.append({'attribute': 'drive', 'value': 'hoạt động bằng điện' if candidate_powered else 'không hoạt động bằng điện'})
                priority += 0 if candidate_powered else 2
        options.append({'code': candidate['code'], 'label': label, 'assumptions': assumptions, 'assumed_attributes': assumed_attributes, 'identified_conditions': identified_conditions, 'catalog_description': candidate['description'], 'evidence_function': evidence_function, 'priority': priority})
    return sorted(options, key=lambda option: option['priority'])[:6]


def option_source_ids(option: dict, chunks: list[dict]) -> list[str]:
    technical = textile_source_ids(option['evidence_function'], chunks)
    prefix = option['code'][:6]
    subheading = [c['chunk_id'] for c in chunks if re.search(r'(?<!\d)' + prefix[:4] + r'[.\s]*' + prefix[4:] + r'(?!\d)', c.get('content', ''))]
    rules = [[c['chunk_id'] for c in chunks if re.search(r'\b(?:qui tắc|quy tắc|rule)\s+' + rule + r'\b', c.get('content', ''), re.I)] for rule in ('1', '6')]
    if not technical or not subheading or not all(rules):
        return []
    return list(dict.fromkeys(technical[:1] + subheading[:1] + rules[0][:1] + rules[1][:1]))


def matching_textile_hypothesis(hypothesis: dict, options: list[dict], chunks: list[dict]) -> bool:
    for option in options:
        ids = option_source_ids(option, chunks)
        if option['assumptions'] and hypothesis.get('code') == option['code'] and ids and set(option['assumptions']).issubset(hypothesis.get('assumptions') or []) and set(ids).issubset(hypothesis.get('source_chunk_ids') or []):
            return True
    return False


def matching_textile_completed(code: str, options: list[dict], chunks: list[dict]) -> bool:
    return any(option['code'] == code and not option['assumptions'] and option_source_ids(option, chunks) for option in options)


def complete_textile_analysis(answer: dict, description: str, options: list[dict], chunks: list[dict]) -> dict:
    supported = [(option, option_source_ids(option, chunks)) for option in options]
    supported = [(option, ids) for option, ids in supported if ids]
    # Do not silently promote a secondary interpretation when the primary
    # function's evidence is absent. Let retrieval/catalog recovery resolve it.
    if not supported or not options or supported[0][0] != options[0]:
        return answer
    hypotheses = []
    for option, ids in supported:
        if option['assumptions']:
            hypotheses.append({'code': option['code'], 'label': option['label'], 'classification_mode': 'single', 'assumptions': option['assumptions'], 'assumed_attributes': option['assumed_attributes'], 'source_chunk_ids': ids,
                'reasoning': 'Giữ đúng nghĩa và cơ cấu mặt hàng đã xác định. ' + '; '.join(option['identified_conditions']) + '. Quy tắc 1 và 6: đối chiếu nhánh danh mục ' + option['catalog_description'] + '. Chỉ thay đổi thuộc tính còn thiếu nêu trong giả định.'})
    first = supported[0][0]
    source_ids = list(dict.fromkeys(source for _, ids in supported for source in ids))
    function = textile_function(description)
    questions = [
        {'question': 'Chức năng của hàng nhập khẩu là gì?', 'answer': '; '.join(first['identified_conditions']), 'source_chunk_ids': source_ids[:1]},
        {'question': 'Máy dệt móc có tự thuộc nhánh dệt kim phẳng không?', 'answer': 'Máy dệt móc làm ren, dây tết hoặc đồ trang trí đối chiếu mục (C)(7) và nhánh Loại khác. Nhánh dệt kim phẳng cần cơ cấu mục (A)(2), không suy ra chỉ từ tên crochet.' if function == 'crochet' else 'So sánh đúng cơ cấu dệt kim tròn, dệt kim phẳng/khâu đính và các máy khác của nhóm; không suy ra từ điều khiển vi tính.', 'source_chunk_ids': source_ids[:2]},
        {'question': 'Máy hoạt động bằng điện không?', 'answer': 'Mô tả đã khai công suất hoặc dẫn động điện; chọn nhánh hoạt động bằng điện.' if drive(description) is True else 'Đã khai không hoạt động bằng điện.' if drive(description) is False else 'Chưa khai dẫn động; đề xuất riêng trường hợp chạy điện và không chạy điện nếu danh mục có các mã đó.', 'source_chunk_ids': []},
        {'question': 'Model và chuỗi kích thước có quyết định phân nhóm không?', 'answer': 'Không tự giải mã số model hoặc chuỗi kích thước liền nhau thành cơ cấu, đường kính trục cuốn hay ngưỡng công suất. Công suất chỉ xác nhận dẫn động điện khi có số và đơn vị khai rõ.', 'source_chunk_ids': []},
        {'question': 'Khi nào dùng phương án mã khác?', 'answer': '; '.join(option['code'] + ': ' + option['label'] for option, _ in supported) + '. Chỉ áp dụng phương án tương ứng với cơ cấu và dẫn động được xác nhận.', 'source_chunk_ids': source_ids[:4]},
    ]
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    summary = ('Đề xuất các mã theo giả định về thuộc tính còn thiếu; ưu tiên ' if hypotheses else 'Xác định mã ') + first['code'] + ' theo nghĩa mặt hàng và chú giải; không giả định lại loại máy đã khai.'
    analysis.update({'summary': summary, 'product_facts': [description], 'decision_questions': questions, 'hypotheses': hypotheses,
        'legal_steps': [{'rule': 'Quy tắc 1', 'application': 'Xác định chức năng của máy hoàn chỉnh thuộc nhóm 84.47 theo nội dung nhóm và đoạn chú giải mô tả cơ cấu.', 'source_chunk_ids': source_ids[:4]},
                        {'rule': 'Quy tắc 6', 'application': 'So sánh phân nhóm dệt kim tròn, dệt kim phẳng/khâu đính và Loại khác; sau đó chọn mã 8 số theo điều kiện dẫn động trong nhánh phù hợp. ' + '; '.join(option['code'] + ': ' + option['catalog_description'] for option, _ in supported), 'source_chunk_ids': source_ids[:5]}],
        'alternatives': [], 'conclusion': 'Đề xuất ' + first['code'] + ((' theo giả định: ' + '; '.join(first['assumptions'])) if hypotheses else ' theo tên hàng, đoạn định nghĩa cơ cấu và dữ kiện dẫn động/đường kính đã khai.'), 'limitations': ['Chỉ giả định dẫn động hoặc đường kính khi dữ kiện đó chưa được khai.'] if hypotheses else [], 'suggested_name': description, 'declaration_details': [description]})
    answer.update({'status': 'CONDITIONAL' if hypotheses else 'COMPLETED', 'recommended_code': None if hypotheses else first['code'], 'reasoning': summary, 'llm_score': .95, 'source_chunk_ids': source_ids, 'legal_analysis': analysis, 'missing_information': []})
    answer.pop('catalog_hints', None)
    return answer
