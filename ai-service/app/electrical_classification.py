"""Check the function branch before rating or national suffix in heading 85.04."""
import re
from .legal_text import contains_phrase


def positive_description(description: str) -> str:
    return re.sub(r'\b(?:not|không)\b[^,;\n.]*', '', description, flags=re.I)


def electrical_function(description: str) -> str | None:
    description = positive_description(description)
    # The inverter fitted to an appliance/cabinet does not classify the whole
    # appliance/cabinet. A part is also not a complete converter.
    if re.search(r'rotary frequency converter|rotary converter|máy biến đổi điện quay|'
                 r'air conditioner|washing machine|refrigerator|máy lạnh|điều hòa|điều hoà|máy giặt|tủ lạnh|'
                 r'control (?:cabinet|panel)|tủ điều khiển|bảng điều khiển|\b(?:pcb|parts? for)\b|mạch in|linh kiện|bộ phận của', description, re.I):
        return None
    if re.search(r'\binverter\b|biến tần|nghịch lưu|rectifier|chỉnh lưu|static converter|biến đổi (?:điện tĩnh|tĩnh điện)|'
                 r'frequency converter|variable[ -]frequency drive|\b(?:vfd|vvvf)\b|\b(?:DC\s*(?:to|/|-|→)\s*(?:DC|AC)|AC\s*(?:to|/|-|→)\s*DC)\b|'
                 r'battery charger|máy nạp (?:ắc|ac)|bộ sạc (?:ắc|pin)|\bUPS\b', description, re.I):
        return 'static_converter'
    if re.search(r'\btransformer\b|máy biến áp|máy biến dòng|máy biến điện', description, re.I):
        return 'transformer'
    if re.search(r'\binductor\b|cuộn cảm|cuộn kháng', description, re.I):
        return 'inductor'
    if re.search(r'\bballast\b|chấn lưu', description, re.I):
        return 'ballast'
    return None


def catalog_electrical_function(candidate: dict) -> str | None:
    parts = [part.strip().lstrip('-').strip().rstrip(':').lower() for part in candidate.get('description', '').split('→')]
    # The four-digit title lists ALL families. It cannot prove a six-digit branch.
    parts = [part for part in parts if not ('cuộn cảm' in part and 'biến đổi' in part and 'máy biến' in part)]
    if any(part == 'bộ phận' for part in parts):
        return 'parts'
    if any(re.search(r'^máy biến đổi (?:tĩnh điện|điện tĩnh)$', part) for part in parts):
        return 'static_converter'
    if any(re.search(r'^máy biến điện (?:sử dụng|khác)|^máy biến áp|^máy biến dòng', part) for part in parts):
        return 'transformer'
    if any(re.search(r'^cuộn cảm|^cuộn kháng', part) for part in parts):
        return 'inductor'
    if any(re.search(r'^chấn lưu', part) for part in parts):
        return 'ballast'
    return None


def function_candidates(description: str, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    function = electrical_function(description)
    if not function:
        return candidates, []
    eligible = [c for c in candidates if catalog_electrical_function(c) == function]
    if function == 'transformer':
        text = positive_description(description)
        if re.search(r'oil[ -]*(?:immersed|filled)|liquid dielectric|điện môi lỏng|biến áp dầu', text, re.I):
            eligible = [c for c in eligible if 'điện môi lỏng' in c['description'].lower()]
        elif re.search(r'dry[ -]*type|biến áp khô|loại khô', text, re.I):
            eligible = [c for c in eligible if 'điện môi lỏng' not in c['description'].lower()]
    excluded = [c for c in candidates if c not in eligible]
    return eligible, excluded


def function_evidence_phrases(function: str) -> list[str]:
    return {
        'static_converter': ['(II) CÁC THIẾT BỊ BIẾN ĐỔI TĨNH ĐIỆN', 'Thiết bị biến đổi dòng điện và tần số'],
        'transformer': ['(I) CÁC MÁY BIẾN ĐIỆN', 'Các máy biến điện là các thiết bị'],
        'inductor': ['(III) CUỘN CẢM'],
        'ballast': ['Chấn lưu dùng cho đèn'],
    }.get(function, [])


def function_source_ids(function: str, chunks: list[dict]) -> list[str]:
    phrases = function_evidence_phrases(function)
    return [c['chunk_id'] for c in chunks if any(contains_phrase(c.get('content', ''), phrase) for phrase in phrases)]


def converter_scenarios(description: str, candidates: list[dict]) -> list[dict]:
    if electrical_function(description) != 'static_converter':
        return []
    raw_description = description
    description = positive_description(description)
    frequency = bool(re.search(r'biến tần|frequency converter|variable[ -]frequency drive|\b(?:vfd|vvvf)\b', description, re.I))
    dc_ac = bool(re.search(r'nghịch lưu|DC\s*(?:to|/|-|→)\s*AC|một chiều.*(?:sang|thành).*xoay chiều', description, re.I))
    rectifier = bool(re.search(r'rectifier|chỉnh lưu|AC\s*(?:to|/|-|→)\s*DC', description, re.I))
    dc_ac = dc_ac or bool(re.search(r'solar|photovoltaic|\bPV\b|điện mặt trời', description, re.I))
    dc_dc = bool(re.search(r'DC\s*(?:to|/|-|→)\s*DC|một chiều.*(?:sang|thành).*một chiều', description, re.I))
    generic_inverter = bool(re.search(r'\binverter\b', description, re.I)) and not (frequency or dc_ac or rectifier)
    adp = bool(re.search(r'computer|telecom|viễn thông|máy tính|xử lý dữ liệu', description, re.I))
    ups = bool(re.search(r'\bUPS\b|nguồn.*liên tục', description, re.I))
    charger = bool(re.search(r'charger|máy nạp|bộ sạc', description, re.I))
    ordinary_use = bool(re.search(r'dùng\s+(?:để\s+)?điều khiển\s+động cơ|for\s+(?:industrial\s+)?motor\s+control', description, re.I)
        or re.search(r'(?:không|not)[^,;\n]{0,100}(?:máy tính|xử lý dữ liệu|computers?|data processing)[^,;\n]{0,80}(?:viễn thông|telecomm)', raw_description, re.I))
    not_charger = bool(re.search(r'(?:không|not)[^,;\n]{0,35}(?:máy nạp|bộ sạc|battery charger)', raw_description, re.I))
    options = []
    for c in candidates:
        if len(c['code']) != 8 or catalog_electrical_function(c) != 'static_converter':
            continue
        text = c['description']
        leaf = text.split('→')[-1].strip().lstrip('-').strip()
        # The declared/defined converter identity is a fact, not a hypothetical
        # alternative to a transformer or a whole control cabinet.
        assumptions = []
        dedicated_adp = bool(re.search(r'dùng cho.*(?:xử lý dữ liệu|viễn thông)', '→'.join(text.split('→')[:-1]), re.I))
        if leaf.lower() == 'loại khác' and not dedicated_adp and (frequency or generic_inverter):
            assumptions += ['Biến tần điện tử biến đổi nguồn xoay chiều thành xoay chiều có tần số thay đổi để điều khiển động cơ công nghiệp',
                            'Không chuyên dùng cho thiết bị xử lý dữ liệu hoặc viễn thông; không phải UPS, máy nạp pin, bộ chỉnh lưu hoặc bộ nghịch lưu DC sang AC thuần túy']
            label, priority = 'Biến tần công nghiệp, phương án ưu tiên', 0
        elif leaf.lower() == 'loại khác' and not dedicated_adp and (dc_dc or (ups and not adp)):
            assumptions += ['Biến đổi điện một chiều sang một chiều ở mức điện áp khác' if dc_dc else 'Bộ nguồn cấp điện liên tục UPS dùng cho hệ thống công nghiệp',
                            'Không chuyên dùng cho các máy xử lý dữ liệu tự động hoặc thiết bị viễn thông']
            label, priority = 'Bộ biến đổi DC sang DC' if dc_dc else 'UPS dùng trong công nghiệp', 0
        elif re.fullmatch(r'bộ nghịch lưu', leaf, re.I) and (dc_ac or generic_inverter) and not frequency and not adp:
            assumptions += ['Chức năng của hàng nhập khẩu là nghịch lưu dòng một chiều DC thành xoay chiều AC, không phải bộ biến đổi AC sang AC thay đổi tần số',
                            'Không chuyên dùng cho thiết bị xử lý dữ liệu hoặc viễn thông']
            label, priority = 'Bộ nghịch lưu DC sang AC', 1 if generic_inverter else 0
        elif re.fullmatch(r'bộ chỉnh lưu khác', leaf, re.I) and rectifier and not frequency and not adp and not charger:
            assumptions += ['Chức năng của hàng nhập khẩu là chỉnh lưu dòng xoay chiều AC thành một chiều DC',
                            'Không chuyên dùng cho thiết bị xử lý dữ liệu hoặc viễn thông; không phải máy nạp pin']
            label, priority = 'Bộ chỉnh lưu', 0
        elif dedicated_adp and adp and ((ups and 'UPS' in leaf) or (not ups and leaf.lower() == 'loại khác')):
            assumptions += ['Thiết bị chuyên dùng cho các máy xử lý dữ liệu tự động hoặc thiết bị viễn thông',
                            'Là bộ nguồn cấp điện liên tục UPS' if ups else 'Không phải bộ nguồn cấp điện liên tục UPS']
            label, priority = 'Bộ biến đổi điện tĩnh chuyên dùng', 0
        else:
            continue
        attributes = []
        if dedicated_adp:
            # ADP/telecom use and a named UPS/converter are already declared.
            assumptions = []
        else:
            mode_assumption, use_assumption = assumptions
            assumptions = []
            if generic_inverter:
                assumptions.append(mode_assumption)
                attributes.append({'attribute': 'conversion_mode', 'value': mode_assumption})
            if not ordinary_use:
                use_assumption = 'Không chuyên dùng cho máy xử lý dữ liệu tự động hoặc thiết bị viễn thông'
                assumptions.append(use_assumption)
                attributes.append({'attribute': 'use', 'value': use_assumption})
            if rectifier and not not_charger:
                assumptions.append('Không phải máy nạp pin hoặc ắc quy')
                attributes.append({'attribute': 'charger.status', 'value': assumptions[-1]})
        options.append({'code': c['code'], 'label': label, 'catalog_description': text, 'assumptions': assumptions,
            'assumed_attributes': attributes, 'priority': priority})
    return sorted(options, key=lambda option: option['priority'])[:3]


def complete_converter_analysis(answer: dict, description: str, options: list[dict], chunks: list[dict]) -> dict:
    if not options:
        return answer
    technical_ids = function_source_ids('static_converter', chunks)
    rule_ids = {rule: [c['chunk_id'] for c in chunks if re.search(r'(?:\b(?:qui|quy)\s+tắc\s+|\brule\s+)' + rule + r'\b', c.get('content', ''), re.I)] for rule in ('1', '6')}
    prefix = options[0]['code'][:6]
    prefix_ids = [c['chunk_id'] for c in chunks if re.search(r'(?<!\d)' + prefix[:4] + r'[.\s]*' + prefix[4:] + r'(?!\d)', c.get('content', ''))]
    if not technical_ids or not prefix_ids or not all(rule_ids.values()):
        return answer
    source_ids = list(dict.fromkeys(technical_ids[:2] + prefix_ids[:1] + rule_ids['1'][:1] + rule_ids['6'][:1]))
    hypotheses = [{'code': o['code'], 'label': o['label'], 'classification_mode': 'single',
                   'assumptions': o['assumptions'], 'assumed_attributes': o['assumed_attributes'], 'source_chunk_ids': source_ids,
                   'reasoning': 'Theo Quy tắc 1 xác định nhóm ' + o['code'][:4] + '; theo chức năng biến đổi điện tĩnh chọn phân nhóm ' + o['code'][:6]
                   + '. Quy tắc 6 yêu cầu đối chiếu đúng nhánh chức năng trước khi chọn đuôi mã. Mô tả danh mục: ' + o['catalog_description']
                   + '. Áp dụng theo những giả định nêu trên; không sử dụng dải kVA của máy biến áp dùng điện môi lỏng để phân loại biến tần.'} for o in options]
    first = hypotheses[0]
    conditional = len(hypotheses) > 1 or any(hypothesis['assumptions'] for hypothesis in hypotheses)
    alternative_text = '; '.join(o['code'] + ': ' + o['label'] for o in options)
    induction_ids = [c['chunk_id'] for c in chunks if 'cảm ứng' in c.get('content', '').lower() and 'máy biến điện' in c.get('content', '').lower()]
    comparison = ('Phân biệt biến đổi điện tĩnh bằng các phần tử biến đổi với máy biến áp hoạt động theo cảm ứng. ' if induction_ids
                  else 'Đối chiếu nội dung giải thích các thiết bị biến đổi điện tĩnh. ')
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    analysis.update({'summary': 'Ưu tiên mã ' + first['code'] + ' theo chức năng và giả định sử dụng nêu rõ; các phương án khác chỉ áp dụng theo điều kiện tương ứng.',
                     'product_facts': [description], 'hypotheses': hypotheses if conditional else [],
                     'legal_steps': [
                         {'rule': 'Quy tắc 1', 'application': 'Thiết bị biến đổi điện tĩnh thuộc nhóm ' + prefix[:4] + ' theo nội dung nhóm và chú giải chức năng.', 'source_chunk_ids': rule_ids['1'][:1] + technical_ids[:1]},
                         {'rule': 'Chú giải nhóm ' + prefix[:4], 'application': comparison + 'Xét chức năng của hàng nhập khẩu hoàn chỉnh; mạch điều khiển phụ trợ không tự biến sản phẩm thành tủ điều khiển điện.', 'source_chunk_ids': list(dict.fromkeys(technical_ids[:2] + induction_ids[:1]))},
                         {'rule': 'Quy tắc 6', 'application': 'Chọn phân nhóm ' + prefix + ' trước khi xét các mã 8 số: ' + alternative_text + '. Chỉ chọn Loại khác sau khi loại các nhánh chuyên biệt cùng cấp.', 'source_chunk_ids': rule_ids['6'][:1] + prefix_ids[:1]},
                     ],
                     'decision_questions': [
                         {'question': 'Chức năng chính là biến áp hay biến đổi điện tĩnh?', 'answer': 'Xét chức năng biến đổi điện tĩnh đã khai hoặc giả định riêng từng phương án. Không suy diễn thành máy biến áp dùng điện môi lỏng từ tên model hoặc công suất.', 'source_chunk_ids': technical_ids[:2]},
                         {'question': 'Chọn phân nhóm sáu số nào?', 'answer': 'Chọn ' + prefix + ' theo chức năng biến đổi điện tĩnh trước khi xét công dụng chuyên biệt và đuôi mã.', 'source_chunk_ids': prefix_ids[:1]},
                         {'question': 'Biến tần AC sang AC hay bộ nghịch lưu DC sang AC?', 'answer': alternative_text + '. Từng phương án nêu rõ chức năng giả định của hàng nhập khẩu hoàn chỉnh.', 'source_chunk_ids': technical_ids[:2]},
                         {'question': 'Chưa khai chất liệu có làm thay đổi nhánh chức năng không?', 'answer': 'Không. Ưu tiên Loại khác chỉ trong nhánh chức năng phù hợp và còn đáp ứng các điều kiện của mã.', 'source_chunk_ids': rule_ids['6'][:1]},
                         {'question': 'Các số trong model có xác nhận công suất và điện áp không?', 'answer': 'Không tự coi số model là thông số có đơn vị đã xác nhận. Chỉ xét ngưỡng công suất, điện áp khi nhánh danh mục thực sự quy định.', 'source_chunk_ids': []},
                     ],
                     'conclusion': 'Đề xuất ' + first['code'] + ' theo giả định: ' + '; '.join(first['assumptions']) + '.',
                     'limitations': ['Các phương án áp dụng theo chức năng và công dụng giả định nêu riêng; đối chiếu cấu hình thực tế để chọn phương án áp dụng.'] if conditional else [],
                     'alternatives': [], 'suggested_name': description,
                     'declaration_details': [description, 'Chức năng và công dụng áp dụng theo giả định của phương án được chọn']})
    if not conditional:
        analysis['summary'] = 'Đề xuất mã ' + first['code'] + ' theo chức năng và công dụng đã khai.'
        analysis['conclusion'] = 'Đề xuất mã HS ' + first['code'] + ' từ thông tin đã khai, không cần giả định thêm.'
        first['reasoning'] = first['reasoning'].replace('Áp dụng theo những giả định nêu trên;', 'Áp dụng theo thông tin đã khai;')
        analysis['decision_questions'][0]['answer'] = 'Tên hàng và công dụng đã khai xác định thiết bị biến đổi điện tĩnh, không phải máy biến áp dùng điện môi lỏng.'
        analysis['decision_questions'][2]['answer'] = alternative_text + '. Chức năng này đã được nêu trong mô tả sản phẩm.'
    answer.update({'status': 'CONDITIONAL' if conditional else 'COMPLETED', 'recommended_code': None if conditional else first['code'],
        'source_chunk_ids': source_ids, 'reasoning': analysis['summary'], 'llm_score': max(.9, float(answer.get('llm_score') or 0)), 'legal_analysis': analysis})
    # Do not retain missing kVA/voltage/dielectric demands from a rejected
    # transformer proposal. The applicable conditional facts are in hypotheses.
    answer['missing_information'] = []
    answer.pop('catalog_hints', None)
    return answer
