"""Catalog hierarchy and conditional selection checks, independent of list order."""
import re


def catalog_branch(candidate: dict) -> tuple:
    # Uncoded intermediate rows carry legal conditions just like numbered parents.
    parents = tuple(part.strip().rstrip(':').lower() for part in candidate.get('description', '').split('→')[:-1])
    return candidate['code'][:6], parents


def has_material(description: str) -> bool:
    return bool(re.search(r'cotton|polyester|nylon|acrylic|silk|wool|steel|iron|brass|bronze|copper|plastic|wood|rubber|alumin\w*|'
                          r'bông|lụa|tơ tằm|\blen\b|thép|\bgang\b|\bsắt\b|\bđồng\b|nhựa|plastic|\bgỗ\b|cao su|\bnhôm\b|sợi (?:tổng hợp|nhân tạo)', description, re.I))


def residual_options(description: str, candidates: list[dict]) -> list[dict]:
    if has_material(description):
        return []
    return [{'code': c['code'], 'catalog_description': c['description']} for c in candidates
            if c['code'].endswith('90') and re.search(r'(?:^|→)\s*loại khác\s*$', c.get('description', ''), re.I)]


def valve_scenarios(description: str, candidates: list[dict]) -> list[dict]:
    """Derive fluid-power valve options from catalog terms, never from fixed codes."""
    if not re.search(r'\bvalve\b|\bvan\b', description, re.I):
        return []
    if re.search(r'water|steam|nước|hơi nước', description, re.I) and not re.search(r'fluid power|truyền động', description, re.I):
        return []
    options = []
    explicit_gate = bool(re.search(r'gate valve|van cổng', description, re.I))
    explicit_manual = bool(re.search(r'manual|hand[- ]operated|bằng tay', description, re.I))
    nonmanual = bool(re.search(r'not (?:manual|hand[- ]operated)|không (?:điều khiển |vận hành )?bằng tay', description, re.I))
    if nonmanual:
        explicit_manual = False
    other_type = nonmanual or bool(re.search(r'butterfly|ball valve|spool|van bướm|van bi|van con trượt|pneumatic actuator|điều khiển bằng khí nén', description, re.I))
    known_ferrous = bool(re.search(r'\bsteel\b|\biron\b|thép|\bsắt\b|\bgang\b', description, re.I))
    known_nonferrous = has_material(description) and not known_ferrous
    diameter_match = re.search(r'(?:φ|ø|\bDN)\s*(\d+(?:[.,]\d+)?)\s*(mm|cm)?', description, re.I)
    # A bare phi measurement is only a plausible mm interpretation. The output
    # must still label both the unit and the measured opening as assumptions.
    diameter_cm = (float(diameter_match[1].replace(',', '.')) / (1 if diameter_match[2] and diameter_match[2].lower() == 'cm' else 10)) if diameter_match else None
    gate_intervals = [re.search(r'trên\s*(\d+(?:[.,]\d+)?)\s*cm.*?không quá\s*(\d+(?:[.,]\d+)?)\s*cm', c.get('description', ''), re.I)
                      for c in candidates if 'van cổng điều khiển bằng tay' in c.get('description', '').lower()]
    inside_gate_range = any(float(m[1].replace(',', '.')) < diameter_cm <= float(m[2].replace(',', '.')) for m in gate_intervals if m) if diameter_cm is not None else None
    known_copper = bool(re.search(r'\bbrass\b|\bbronze\b|\bcopper\b|\bđồng\b', description, re.I))
    known_plastic = bool(re.search(r'\bplastic\b|nhựa', description, re.I))
    small_code = None
    for c in candidates:
        leaf = c.get('description', '').split('→')[-1]
        copper_limit = re.search(r'bằng đồng.*?không quá\s*([\d.,]+)\s*cm', leaf, re.I)
        plastic_limits = re.search(r'(?:bằng plastic|nhựa).*?từ\s*([\d.,]+)\s*cm.*?đến\s*([\d.,]+)\s*cm', leaf, re.I)
        if diameter_cm is not None and ((known_copper and copper_limit and diameter_cm <= float(copper_limit[1].replace(',', '.')))
                or (known_plastic and plastic_limits and float(plastic_limits[1].replace(',', '.')) <= diameter_cm <= float(plastic_limits[2].replace(',', '.')))):
            small_code = c['code']
    for c in candidates:
        text = c.get('description', '')
        if len(c['code']) != 8 or not re.search(r'truyền động.*(?:khí nén|thuỷ lực|thủy lực)', text, re.I):
            continue
        parents, leaf = text.rsplit('→', 1) if '→' in text else ('', text)
        manual_gate = 'van cổng điều khiển bằng tay' in parents.lower()
        broad_other = bool(re.fullmatch(r'\s*loại khác\s*', leaf, re.I)) and not manual_gate and not re.search(r'đường kính|bằng (?:đồng|plastic)', parents, re.I)
        medium = 'dầu thủy lực' if re.search(r'hydraulic|thủy lực|thuỷ lực', description, re.I) and not re.search(r'pneumatic|khí nén', description, re.I) else 'khí nén'
        assumptions = [f'Van chuyên dùng trong hệ truyền động {medium}, chất lưu nén cung cấp năng lượng']
        if c['code'] == small_code:
            assumptions += [leaf.strip(), 'Kích thước đã khai là đường kính trong cửa van, không phải đường kính thân hoặc bộ dẫn động']
            label, priority = 'Van có chất liệu và đường kính trong thuộc nhánh nhỏ', 0
        elif manual_gate:
            if other_type or inside_gate_range is False:
                continue
            ferrous = bool(re.search(r'bằng sắt hoặc thép', leaf, re.I))
            if (known_ferrous and not ferrous) or (known_nonferrous and ferrous):
                continue
            interval = re.search(r'đường kính[^→]+', parents, re.I)
            if not interval:
                continue
            assumptions += ['Van cổng điều khiển bằng tay', interval.group().strip().rstrip(':')]
            assumptions += ['Thân van bằng sắt hoặc thép'] if ferrous else [
                'Thân van bằng vật liệu khác sắt hoặc thép' + (', theo chất liệu đã khai' if known_nonferrous else ', giả định bằng đồng')]
            label = 'Van cổng bằng sắt hoặc thép, vận hành tay' if ferrous else 'Van cổng bằng đồng, vận hành tay'
            priority = 1 if ferrous else 2
        elif broad_other:
            if small_code or (explicit_gate and explicit_manual and inside_gate_range is not False):
                # A specified gate/manual product must first test the narrower branch.
                continue
            assumptions += ['Van cổng điều khiển bằng tay có đường kính trong ngoài khoảng của nhánh van cổng nêu riêng' if explicit_gate and explicit_manual else 'Van điều khiển tự động, không phải van cổng điều khiển bằng tay',
                            'Không thuộc nhánh van bằng đồng hoặc plastic có đường kính trong nhỏ được mô tả riêng']
            label, priority = 'Van truyền động loại khác, phương án ưu tiên', 0
        else:
            continue
        options.append({'code': c['code'], 'label': label, 'catalog_description': text,
                        'assumptions': assumptions, 'priority': priority, 'manual_gate': manual_gate})
    return sorted(options, key=lambda option: option['priority'])[:3]


def matching_valve_hypothesis(hypothesis: dict, options: list[dict], chunks: list[dict]) -> bool:
    code = re.sub(r'\D', '', str(hypothesis.get('code', '')))
    option = next((item for item in options if item['code'] == code), None)
    if not option:
        return False
    # Require the complete physical assumptions, not a vague "diameter fits".
    assumptions = {value.strip().casefold() for value in hypothesis.get('assumptions', []) if isinstance(value, str)}
    if not all(value.casefold() in assumptions for value in option['assumptions']):
        return False
    heading = code[:4]
    source_ids = {c['chunk_id'] for c in chunks if re.search(r'(?<!\d)' + heading[:2] + r'[.\s]*' + heading[2:] + r'(?!\d)', c.get('content', ''))}
    return (hypothesis.get('classification_mode', 'single') == 'single'
            and bool(hypothesis.get('reasoning')) and bool(source_ids.intersection(hypothesis.get('source_chunk_ids') or [])))


def valve_review_errors(hypotheses: list[dict], options: list[dict], chunks: list[dict]) -> bool:
    valid_codes = {re.sub(r'\D', '', str(h.get('code', ''))) for h in hypotheses if isinstance(h, dict)
                   and matching_valve_hypothesis(h, options, chunks)}
    return any(option['code'] not in valid_codes for option in options)


def complete_valve_analysis(answer: dict, description: str, options: list[dict], chunks: list[dict]) -> dict:
    """Build supported conditional cases when the model omits a branch.

    These are explicit physical assumptions, never asserted product facts. Only
    supplied catalog descriptions and actual heading/Rule 1/Rule 6 text are used.
    """
    if not options:
        return answer
    heading = options[0]['code'][:4]
    heading_ids = [c['chunk_id'] for c in chunks if re.search(r'(?<!\d)' + heading[:2] + r'[.\s]*' + heading[2:] + r'(?!\d)', c.get('content', ''))]
    rule_ids = {rule: [c['chunk_id'] for c in chunks if re.search(r'(?:\b(?:qui|quy)\s+tắc\s+|\brule\s+)' + rule + r'\b', c.get('content', ''), re.I)] for rule in ('1', '6')}
    if not heading_ids or not all(rule_ids.values()):
        return answer
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    hypotheses = []
    for option in options:
        path = option['catalog_description']
        explanation = 'Đối chiếu danh mục từ nhánh cha đến mã 8 số theo Quy tắc 1 và 6: ' + path + '. '
        if option['manual_gate']:
            explanation += 'Chỉ áp dụng khi đồng thời thỏa cấu tạo van cổng, vận hành bằng tay, đường kính trong cửa và chất liệu đã giả định; kích thước riêng lẻ không quyết định mã.'
        else:
            explanation += 'Theo các giả định nêu trên, không thuộc những nhánh cụ thể đứng trước cùng cấp nên chọn nhánh này.'
        hypotheses.append({'code': option['code'], 'label': option['label'], 'classification_mode': 'single',
                           'assumptions': option['assumptions'], 'reasoning': explanation,
                           'source_chunk_ids': list(dict.fromkeys(heading_ids[:2] + rule_ids['1'][:1] + rule_ids['6'][:1]))})
    first = hypotheses[0]
    steps = analysis.get('legal_steps') if isinstance(analysis.get('legal_steps'), list) else []
    for rule in ('1', '6'):
        if not any(isinstance(step, dict) and re.search(r'(?:quy tắc|rule)\s+' + rule + r'\b', str(step.get('rule', '')), re.I) for step in steps):
            steps.append({'rule': 'Quy tắc ' + rule, 'application': 'Xét nội dung nhóm và chú giải liên quan.' if rule == '1' else 'So sánh phân nhóm cùng cấp, kiểm tra toàn bộ điều kiện nhánh cha trước mã 8 số.', 'source_chunk_ids': rule_ids[rule]})
    analysis.update({'hypotheses': hypotheses, 'legal_steps': steps, 'product_facts': [description],
                     'summary': f'Đề xuất có điều kiện mã {first["code"]}; các mã khác áp dụng theo những giả định cấu tạo, vận hành và chất liệu cụ thể.',
                     'conclusion': f'Ưu tiên {first["code"]} theo giả định: ' + '; '.join(first['assumptions']) + '.',
                     'decision_questions': [
                         {'question': 'Van có chuyên dùng trong hệ truyền động lưu chất không?',
                          'answer': first['assumptions'][0] + '. Tên hoặc cách dẫn động đơn lẻ chưa xác nhận chức năng này.', 'source_chunk_ids': heading_ids[:2]},
                         {'question': 'Loại van và cách vận hành đã được khai rõ chưa?',
                          'answer': 'Chọn phương án ưu tiên theo giả định: ' + '; '.join(first['assumptions'][1:]), 'source_chunk_ids': heading_ids[:2]},
                         {'question': 'Kích thước đã khai có phải đường kính trong cửa van không?',
                          'answer': ('Hiểu φ350 là 350 mm = 35 cm đường kính trong cửa chỉ là giả định; đơn vị và vị trí đo chưa được xác nhận.' if re.search(r'φ\s*350\b', description, re.I) else 'Đối chiếu kích thước đã khai với đường kính TRONG cửa. Nếu đơn vị hoặc vị trí đo chưa rõ, ghi nhận chúng là giả định.'), 'source_chunk_ids': heading_ids[:2]},
                         {'question': 'Chưa khai chất liệu thì ưu tiên mã nào?',
                          'answer': ('Ưu tiên Loại khác đuôi 90 nếu có trong nhánh phù hợp; các chất liệu cụ thể là phương án phụ.' if not has_material(description) else 'Giữ nguyên chất liệu đã khai, xét nhánh có đủ điều kiện cấu tạo, vận hành và kích thước.'), 'source_chunk_ids': rule_ids['6'][:1]},
                     ]})
    answer.update({'status': 'CONDITIONAL', 'recommended_code': None, 'legal_analysis': analysis})
    return answer
