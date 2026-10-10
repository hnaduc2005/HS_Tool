"""Keep decorative surface treatment separate from a declared plastic layer.

Interpret the whole article and its use before choosing a coating family. Codes
and citations come from supplied catalog rows and sources. Bare PU is never
proof of laminated plastic film; shorthand G is preserved without inventing gsm.
"""
import re
from .document_normalization import searchable_text


def positive_match(pattern: str, text: str):
    return next((match for match in re.finditer(pattern, text, re.I)
        if not re.search(r'(?:không|chưa|not|non)[\s-]*(?:(?:phải|là|dùng|để|được)[\s-]+)*$', text[max(0, match.start() - 25):match.start()], re.I)), None)


def paper_profile(description: str) -> dict | None:
    text = searchable_text(description)
    first = searchable_text(re.split(r'[,;\n]', description, maxsplit=1)[0])
    if not re.search(r'(?<!\w)(?:giấy|bìa|paper|paperboard)(?!\w)', first, re.I):
        return None
    if re.search(r'(?<!\w)(?:máy|machine|printer|board|ván)(?!\w)', first, re.I):
        return None
    coating = positive_match(r'(?:phủ|tráng|tẩm|coated?\s*(?:with|by)?|covered\s*(?:with|by)?)\s*(?:bằng\s+)?(?:(?:lớp|nhựa|màng|film)\s+){0,3}(PU|polyurethane?|polyuretan|PVC|PE|PP|plastic|nhựa)\b', text)
    # Also accept common English construction, e.g. PU-coated decorative paper.
    if not coating:
        coating = positive_match(r'\b(PU|polyurethane?|PVC|PE|PP|plastic)[ -]coated\b', first)
    if not coating:
        return None
    width = re.search(r'(\d+(?:[.,]\d+)?)\s*(mm|cm)\b', text, re.I)
    # Width is explicit when labelled, or in a one-dimensional paper QC spec.
    if width and re.search(r'[x×*]\s*\d+\s*(?:mm|cm)', text[width.end():], re.I):
        width = None
    width_cm = float(width[1].replace(',', '.')) / (10 if width[2].lower() == 'mm' else 1) if width else None
    gsm = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:g(?:\s*/\s*m(?:2|²)|sm))\b', text, re.I)
    range_gsm = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:g(?:\s*/\s*m(?:2|²)|sm))?\s*[~–-]\s*(\d+(?:[.,]\d+)?)\s*g(?:\s*/\s*m(?:2|²)|sm)\b', text, re.I)
    shorthand = re.search(r'(\d+(?:[.,]\d+)?)\s*G\s*[~–-]\s*(\d+(?:[.,]\d+)?)\s*G\b', text, re.I)
    grammage = tuple(float(range_gsm[index].replace(',', '.')) for index in (1, 2)) if range_gsm else (float(gsm[1].replace(',', '.')),) * 2 if gsm else None
    declared_range = tuple(float(shorthand[index].replace(',', '.')) for index in (1, 2)) if shorthand else None
    bleached = False if re.search(r'không\s*tẩy trắng|chưa\s*tẩy trắng|\bunbleached\b', text, re.I) else True if re.search(r'tẩy trắng|\bbleached\b', text, re.I) else None
    adhesive = 'self' if positive_match(r'tự\s*dính|self[ -]adhesive', text) else 'adhesive' if positive_match(r'(?:phủ|tráng|quét)\s*(?:lớp\s*)?keo|adhesive[ -]coated|gummed', text) else 'none' if re.search(r'không\s*(?:tự dính|(?:phủ|tráng|quét) keo)|non[ -]adhesive', text, re.I) else None
    wall = bool(positive_match(r'giấy\s*dán\s*tường|wallpaper|dùng\s*(?:để\s*)?dán\s*tường', text))
    floor = bool(positive_match(r'(?:phủ|lót)\s*sàn|floor\s*cover', text))
    board = bool(re.search(r'bề\s*mặt\s*ván|furniture|panel\s*surface|laminat.*(?:board|panel)', text, re.I))
    use = positive_match(r'(?:dùng|sử dụng)\s+[^,;\n]+', description)
    form = 'roll' if positive_match(r'dạng\s*cuộn|\bin rolls?\b', text) else 'sheet' if positive_match(r'tờ\s*(?:hình\s*)?chữ nhật|rectangular\s*sheets?', text) else 'other' if positive_match(r'cắt\s*(?:thành\s*)?hình\s*tròn|circular\s*(?:cut|sheets?)', text) else None
    thick = re.search(r'(?:lớp\s*(?:phủ\s*)?(?:PU|PVC|plastic|nhựa)|plastic\s*layer)[^,;\n]{0,35}?(?:chiếm|constitut|dày)[^,;\n]{0,15}?(\d+(?:[.,]\d+)?)\s*%[^,;\n]{0,25}(?:tổng\s*độ\s*dày|total\s*thickness)', text, re.I)
    thickness_ratio = float(thick[1].replace(',', '.')) if thick else None
    plastic_layer = bool(positive_match(r'(?:ghép|phủ|tráng|ép|bọc)\s*(?:bằng\s*)?(?:lớp\s*)?(?:màng|film)\s*(?:plastic|nhựa|PU|PVC|PE|PP)|(?:plastic|polyurethane?|PU|PVC|PE|PP)[ -](?:film|laminat)|coated\s+with\s+(?:a\s+)?plastic', text))
    decorated = bool(re.search(r'giấy\s*trang\s*trí|decorative\s*paper|in\s*(?:hoa văn|vân gỗ)|wood[ -]grain', text, re.I))
    decorative_finish = decorated and board and not plastic_layer and coating[1].upper() in ('PU', 'POLYURETHANE', 'POLYURETHAN', 'POLYURETAN') and not wall and not floor and form != 'other' and (thickness_ratio is None or thickness_ratio <= 50) and adhesive not in ('self', 'adhesive')
    return {'coating': coating[1].upper(), 'coating_quote': coating[0], 'width': width.group(0) if width else '', 'width_cm': width_cm,
            'grammage': grammage, 'grammage_quote': (range_gsm or gsm).group(0) if range_gsm or gsm else '',
            'declared_range': declared_range, 'shorthand_quote': shorthand.group(0) if shorthand else '', 'bleached': bleached,
            'adhesive': adhesive, 'wall': wall, 'floor': floor, 'board': board, 'use_quote': use.group(0) if use else '', 'form': form, 'thickness_ratio': thickness_ratio,
            'plastic_layer': plastic_layer, 'decorative_finish': decorative_finish}


def paper_candidates(profile: dict, candidates: list[dict]) -> list[dict]:
    if profile['thickness_ratio'] is not None and profile['thickness_ratio'] > 50:
        return [candidate for candidate in candidates if candidate['code'].startswith('39')]
    if profile['wall']:
        return [candidate for candidate in candidates if candidate['code'].startswith('4814')]
    if profile['form'] == 'other':
        return candidates
    prefix = '481141' if profile['adhesive'] == 'self' else '481149' if profile['adhesive'] == 'adhesive' else '481190' if profile['decorative_finish'] else '48115' if profile['plastic_layer'] else '4811'
    selected = [candidate for candidate in candidates if candidate['code'].startswith(prefix)]
    if profile['grammage'] and profile['grammage'][1] <= 150 or profile['bleached'] is False:
        selected = [candidate for candidate in selected if not candidate['code'].startswith('481151')]
    if profile['grammage'] and profile['grammage'][0] > 150 and profile['bleached'] is True:
        selected = [candidate for candidate in selected if not candidate['code'].startswith('481159')]
    if profile['width_cm'] is not None and (profile['width_cm'] > 36 or profile['form'] == 'roll' and profile['width_cm'] > 15):
        selected = [candidate for candidate in selected if not re.search(r'không\s*(?:quá|có\s*chiều\s*nào\s*trên)\s*(?:15|36)\s*cm', candidate.get('description', ''), re.I)]
    if profile['width_cm'] is not None and profile['form'] == 'roll' and profile['width_cm'] <= 15:
        selected = [candidate for candidate in selected if re.search(r'không\s*quá\s*15\s*cm', candidate.get('description', ''), re.I)]
    if profile['board'] and not profile['floor']:
        selected = [candidate for candidate in selected if not re.search(r'phủ\s*sàn|đóng\s*gói\s*thực\s*phẩm', candidate.get('description', ''), re.I)]
    return selected


def paper_missing(profile: dict) -> list[str]:
    missing = []
    if profile['decorative_finish']:
        # These 4811.90 children depend on size and product family, not on a
        # 150 gsm threshold, bleaching or the polymer name alone. Both a roll
        # and a rectangular sheet with a stated dimension >36cm reach the same
        # ordinary large-size child; asking for packaging cannot change it.
        if profile['width_cm'] is None: missing.append('width')
        elif profile['width_cm'] <= 36 and profile['form'] != 'roll': missing.append('dimensions.length')
        return missing
    if profile['adhesive'] in ('self', 'adhesive'):
        if profile['width_cm'] is None: missing.append('width')
        elif profile['width_cm'] <= 36 and profile['form'] != 'roll': missing.append('dimensions.length')
        return missing
    if not profile['plastic_layer'] and profile['adhesive'] not in ('self', 'adhesive'):
        return ['coating.form']
    if not profile['form']: missing.append('form')
    if profile['width_cm'] is None: missing.append('width')
    elif profile['width_cm'] <= 36 and profile['form'] != 'roll': missing.append('dimensions.length')
    if profile['adhesive'] is None: missing.append('adhesive.status')
    if profile['thickness_ratio'] is None: missing.append('coating.thickness_ratio')
    if profile['grammage'] is None: missing.append('grammage.unit' if profile['declared_range'] else 'grammage')
    high = (profile['grammage'] or profile['declared_range'])
    if profile['bleached'] is None and (high is None or high[1] > 150): missing.append('bleaching')
    return missing


def complete_paper_analysis(answer: dict, description: str, candidates: list[dict], chunks: list[dict], understanding: dict | None) -> dict:
    profile = paper_profile(description)
    if profile and profile['decorative_finish']:
        return complete_decorative_paper(answer, description, profile, candidates, chunks)
    if not profile or not profile['plastic_layer'] or profile['wall'] or profile['floor'] or profile['adhesive'] in ('self', 'adhesive') or profile['form'] == 'other' or (profile['thickness_ratio'] is not None and profile['thickness_ratio'] > 50): return answer
    heading = [chunk['chunk_id'] for chunk in chunks if re.search(r'48[.]11\s*[-–]', chunk.get('content', ''))]
    coating = [chunk['chunk_id'] for chunk in chunks if re.search(r'4811[.]5[19]', chunk.get('content', '')) and 'plastic' in chunk.get('content', '').lower()]
    thickness = [chunk['chunk_id'] for chunk in chunks if re.search(r'(?:một nửa|half).*(?:độ dày|thickness)|(?:độ dày|thickness).*(?:một nửa|half)', searchable_text(chunk.get('content', '')), re.I)]
    rules = {rule: [chunk['chunk_id'] for chunk in chunks if re.search(r'(?:\b(?:qui|quy)\s+tắc\s+|\brule\s+)' + rule + r'\b', chunk.get('content', ''), re.I)] for rule in ('1', '6')}
    if not heading or not coating or not thickness or not all(rules.values()): return answer
    eligible = paper_candidates(profile, candidates)
    # Evaluate ordinary wide and small-size children by their supplied ancestor
    # conditions. Never turn a "dùng dán" purpose into confirmed self-adhesion.
    options = []
    mass = profile['grammage'] or profile['declared_range']
    for candidate in eligible:
        code, label = candidate['code'], candidate.get('description', '')
        if len(code) != 8 or not re.search(r'(?:^|→)\s*(?:-\s*)*loại khác\s*$', label, re.I): continue
        if not code.startswith(('481151', '481159', '481141', '481149')): continue
        high = code.startswith('481151')
        if high and (profile['bleached'] is False or mass is not None and mass[1] <= 150): continue
        if not high and code.startswith('481159') and mass is not None and mass[0] > 150 and profile['bleached'] is True: continue
        small = bool(re.search(r'không\s*quá\s*15\s*cm', label, re.I))
        if small and profile['width_cm'] is not None and profile['width_cm'] > 36: continue
        if profile['floor'] and 'phủ sàn' not in label.lower(): continue
        assumptions, attributes = [], []
        def assume(attribute, value):
            assumptions.append(value)
            attributes.append({'attribute': attribute, 'value': value})
        if not profile['form']: assume('form', 'Giấy ở dạng cuộn hoặc tờ hình chữ nhật, không cắt thành hình dạng khác')
        if profile['width_cm'] is not None and profile['width_cm'] <= 36 and profile['form'] != 'roll':
            assume('dimensions.length', 'Tờ không có chiều nào trên 36 cm; nếu dạng cuộn, khổ không quá 15 cm' if small
                else 'Giấy dạng tờ hình chữ nhật có chiều còn lại trên 36 cm' if profile['width_cm'] <= 15
                else 'Nếu dạng tờ, chiều còn lại trên 36 cm; hoặc giấy dạng cuộn có khổ trên 15 cm')
        if profile['width_cm'] is None: assume('width', 'Khổ cuộn trên 15 cm hoặc tờ có một chiều trên 36 cm' if not small else 'Cuộn không quá 15 cm hoặc tờ không có chiều nào trên 36 cm')
        if profile['adhesive'] is None: assume('adhesive.status', 'Lớp PU/plastic là lớp phủ bề mặt, không phải lớp keo; giấy không tự dính')
        if profile['thickness_ratio'] is None: assume('coating.thickness_ratio', 'Độ dày lớp plastic không vượt quá một nửa tổng độ dày')
        if profile['grammage'] is None:
            if profile['declared_range']: assume('grammage.unit', 'Ký hiệu ' + profile['shorthand_quote'] + ' được hiểu là định lượng g/m²')
            else: assume('grammage', 'Định lượng trên 150 g/m²' if high else 'Định lượng không quá 150 g/m²')
        if high and profile['bleached'] is None: assume('bleaching', 'Giấy đã tẩy trắng và định lượng trên 150 g/m²')
        if not assumptions:
            options.append({'code': code, 'label': 'Giấy phủ plastic theo dữ kiện đã khai', 'assumptions': [], 'assumed_attributes': [], 'classification_mode': 'single'})
        else:
            options.append({'code': code, 'label': 'Giấy phủ plastic, ' + ('đã tẩy trắng trên 150 g/m²' if high else 'loại khác'),
                'assumptions': assumptions, 'assumed_attributes': attributes, 'classification_mode': 'single'})
        options[-1].update({'reasoning': 'Quy tắc 1: giấy đã phủ plastic thuộc nhóm 48.11 khi đáp ứng điều kiện lớp phủ. '
            + 'Quy tắc 6: đối chiếu điều kiện tẩy trắng VÀ định lượng trên 150 g/m² trước khi chọn nhánh; khổ ' + (profile['width'] or 'giả định')
            + ' được so sánh với 15 cm cho cuộn và 36 cm cho tờ. Công dụng ' + ('dán bề mặt ván' if profile['board'] else 'giấy phủ plastic')
            + ' không tự xác nhận keo tự dính. Mô tả đầy đủ trong danh mục: ' + label,
            'source_chunk_ids': list(dict.fromkeys(heading[:1] + coating[:1] + thickness[:1] + rules['1'][:1] + rules['6'][:1]))})
    if not options: return answer
    options = options[:6]
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    conditional = len(options) > 1 or any(option['assumptions'] for option in options)
    analysis.update({'summary': 'Đề xuất ' + ', '.join(option['code'] for option in options) + ' theo lớp phủ, định lượng và kích thước của giấy.',
        'product_facts': [description], 'hypotheses': options if conditional else [],
        'legal_steps': [
            {'rule': 'Quy tắc 1', 'application': 'Chọn nhóm 48.11 cho giấy được tráng/phủ plastic ở dạng phù hợp; việc dùng dán lên ván không biến giấy thành gỗ hoặc giấy dán tường.', 'source_chunk_ids': rules['1'][:1] + heading[:1]},
            {'rule': 'Chú giải nhóm 48.11, điều kiện lớp phủ', 'application': 'Lớp plastic không vượt quá một nửa tổng độ dày; nếu vượt ngưỡng phải xem lại Chương 39, không áp dụng phương án giấy dưới đây.', 'source_chunk_ids': thickness[:1]},
            {'rule': 'Quy tắc 6', 'application': 'Phân nhóm 4811.51 yêu cầu đồng thời tẩy trắng và định lượng trên 150 g/m². Khi định lượng không quá 150 g/m², tình trạng tẩy trắng không đổi nhánh 4811.59. Đối chiếu khổ cuộn, kích thước tờ và nhánh công dụng trước khi chọn mã tám số.', 'source_chunk_ids': rules['6'][:1] + coating[:1]}],
        'decision_questions': [
            {'question': 'Vật liệu hàng nhập là gì?', 'answer': 'Giấy được phủ ' + profile['coating'] + '; vân gỗ và bề mặt ván là hoa văn/công dụng, không phải vật liệu của giấy.', 'source_chunk_ids': heading[:1]},
            {'question': '“Dùng dán” có nghĩa giấy tự dính không?', 'answer': 'Không tự suy ra. ' + ('Đã khai giấy không tự dính.' if profile['adhesive'] == 'none' else 'Phương án giấy phủ plastic giả định lớp phủ không phải keo và giấy không tự dính.'), 'source_chunk_ids': coating[:1]},
            {'question': 'Định lượng và khổ giấy được xử lý thế nào?', 'answer': ('Giữ nguyên định lượng ' + profile['grammage_quote'] + ' đã khai.' if profile['grammage'] else 'Giả định định lượng theo từng phương án; không coi đơn vị G đã xác nhận là g/m².') + (' Khổ ' + profile['width'] + ' = ' + str(profile['width_cm']) + ' cm; kiểm tra đúng ngưỡng cuộn/tờ.' if profile['width_cm'] is not None else ' Khổ và dạng giấy áp dụng theo từng giả định.'), 'source_chunk_ids': coating[:1]},
            {'question': 'Có cần biết giấy nền đã tẩy trắng không?', 'answer': 'Chỉ ảnh hưởng nhánh 4811.51 khi định lượng trên 150 g/m². Ở định lượng không quá 150 g/m², không đòi dữ kiện tẩy trắng để chọn nhánh 4811.59.', 'source_chunk_ids': coating[:1]},
            {'question': 'Lớp phủ có làm đổi chương không?', 'answer': ('Đã khai lớp plastic chiếm ' + str(profile['thickness_ratio']) + '% tổng độ dày, không vượt quá một nửa.' if profile['thickness_ratio'] is not None else 'Giả định lớp plastic không vượt quá một nửa tổng độ dày.') + ' Lớp phủ vượt ngưỡng cần xét lại Chương 39.', 'source_chunk_ids': thickness[:1]}],
        'conclusion': ('Theo các giả định đã nêu, đề xuất ' if conditional else 'Đề xuất ') + options[0]['code'] + '.',
        'limitations': list(dict.fromkeys(assumption for option in options for assumption in option['assumptions'])), 'alternatives': []})
    answer.update({'status': 'CONDITIONAL' if conditional else 'COMPLETED', 'recommended_code': None if conditional else options[0]['code'],
        'llm_score': max(.85, float(answer.get('llm_score') or 0)), 'source_chunk_ids': options[0]['source_chunk_ids'],
        'missing_information': paper_missing(profile) if conditional else [], 'legal_analysis': analysis})
    answer.pop('catalog_hints', None)
    return answer


def complete_decorative_paper(answer: dict, description: str, profile: dict, candidates: list[dict], chunks: list[dict]) -> dict:
    if profile['wall'] or profile['floor'] or profile['form'] == 'other' or profile['thickness_ratio'] is not None and profile['thickness_ratio'] > 50: return answer
    heading = [chunk['chunk_id'] for chunk in chunks if re.search(r'48[.]11\s*[-–]', chunk.get('content', '')) and '4811.90' in chunk.get('content', '')]
    decoration = [chunk['chunk_id'] for chunk in chunks if re.search(r'tạo vân bề mặt|in mẫu hình|surface.decorat', searchable_text(chunk.get('content', '')), re.I)]
    rules = {rule: [chunk['chunk_id'] for chunk in chunks if re.search(r'(?:\b(?:qui|quy)\s+tắc\s+|\brule\s+)' + rule + r'\b', chunk.get('content', ''), re.I)] for rule in ('1', '6')}
    if not heading or not decoration or not all(rules.values()): return answer
    ordinary = [candidate for candidate in paper_candidates(profile, candidates) if len(candidate['code']) == 8 and candidate['code'].startswith('481190')
        and re.search(r'(?:^|→)\s*(?:-\s*)*loại khác\s*$', candidate.get('description', ''), re.I)
        and not re.search(r'phủ sàn|giấy tạo vân\s*\(SEN\)|tấm xenlulo hoặc màng', candidate.get('description', ''), re.I)]
    if len(ordinary) != 1 or paper_missing(profile): return answer
    code = ordinary[0]['code']
    size_application = 'vượt ngưỡng cuộn 15 cm và tờ 36 cm' if profile['width_cm'] > 36 else 'vượt ngưỡng cuộn 15 cm' if profile['width_cm'] > 15 else 'không quá ngưỡng cuộn 15 cm'
    ids = list(dict.fromkeys(heading[:1] + decoration[:1] + rules['1'][:1] + rules['6'][:1]))
    summary = 'Giấy trang trí xử lý bề mặt phủ ' + profile['coating'] + ', dùng dán giả vân gỗ trên bề mặt ván; đề xuất mã ' + code + ' theo thông tin đã khai.'
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    analysis.update({'summary': summary, 'product_facts': [description], 'hypotheses': [],
        'legal_steps': [
            {'rule': 'Quy tắc 1', 'application': 'Đọc toàn bộ tên hàng, xử lý bề mặt, quy cách và công dụng: hàng nhập là giấy trang trí phủ PU để dán lên ván. Nhóm 48.11 bao gồm giấy đã trang trí hoặc in bề mặt. Ván và vân gỗ không phải vật liệu của giấy.', 'source_chunk_ids': rules['1'][:1] + heading[:1] + decoration[:1]},
            {'rule': 'Chú giải nhóm 48.11, giấy trang trí bề mặt', 'application': 'Đối chiếu mục (D) về giấy in mẫu hình và tạo vân bề mặt. Phủ PU trong mô tả giấy trang trí là xử lý bề mặt; tên polymer riêng lẻ không xác nhận hàng là giấy ghép/phủ màng plastic, giấy tự dính, tấm phủ sàn hay giấy dán tường.', 'source_chunk_ids': decoration[:1] + heading[:1]},
            {'rule': 'Quy tắc 6', 'application': 'Chọn phân nhóm 4811.90 theo mặt hàng đã hiểu, rồi đối chiếu các nhánh quốc gia. Khổ ' + profile['width'] + ' = ' + str(profile['width_cm']) + ' cm ' + size_application + '. Giấy trang trí dán mặt ván không thuộc các nhánh tấm phủ sàn hoặc tấm xenlulo. Danh mục đầy đủ: ' + ordinary[0]['description'] + '. Ký hiệu ' + (profile['grammage_quote'] or profile['shorthand_quote'] or 'định lượng đã khai') + ' được giữ nguyên; nhánh này không yêu cầu giả định ngưỡng 150 g/m² hay tình trạng tẩy trắng.', 'source_chunk_ids': rules['6'][:1] + heading[:1]}],
        'decision_questions': [
            {'question': 'Toàn bộ mặt hàng được mô tả là gì?', 'answer': 'Giấy trang trí phủ PU dùng dán giả vân gỗ lên mặt ván, không phải ván gỗ hoặc nguyên liệu PU riêng.', 'source_chunk_ids': heading[:1]},
            {'question': 'Tên PU có tự xác định nhánh phủ màng plastic không?', 'answer': 'Không. Phải phân biệt xử lý bề mặt giấy trang trí với giấy ghép/phủ màng plastic được khai rõ. Mô tả này đối chiếu nhánh giấy trang trí bề mặt.', 'source_chunk_ids': heading[:1] + decoration[:1]},
            {'question': 'Khổ giấy và quy cách có làm thay đổi mã không?', 'answer': 'Khổ ' + profile['width'] + ' ' + size_application + '. Giữ nguyên ' + (profile['grammage_quote'] or profile['shorthand_quote'] or 'quy cách đã khai') + '; không tự bổ sung đơn vị hay ngưỡng không áp dụng.', 'source_chunk_ids': rules['6'][:1]},
            {'question': 'Có cần thêm giả định để chọn mã không?', 'answer': 'Không. Dữ kiện nhận diện, xử lý bề mặt, khổ và công dụng đã xác định nhánh áp dụng; nhãn hiệu hoặc model không phải điều kiện của mã.', 'source_chunk_ids': heading[:1]}],
        'alternatives': [], 'conclusion': 'Đề xuất mã HS ' + code + ' từ mô tả đầy đủ của sản phẩm.', 'limitations': []})
    answer.update({'status': 'COMPLETED', 'recommended_code': code, 'reasoning': summary, 'llm_score': .9,
        'alternatives': [], 'source_chunk_ids': ids, 'missing_information': [], 'legal_analysis': analysis})
    answer.pop('catalog_hints', None)
    return answer


def paper_comparisons(description: str, candidates: list[dict], chunks: list[dict]) -> list[dict]:
    """Compare excluded catalog children without admitting them as proposals."""
    profile = paper_profile(description)
    if not profile or not profile['decorative_finish'] or paper_missing(profile): return []
    heading = [chunk['chunk_id'] for chunk in chunks if re.search(r'48[.]11\s*[-–]', chunk.get('content', ''))
        and re.search(r'4811[.]59', chunk.get('content', '')) and 'plastic' in chunk.get('content', '').lower()]
    rules = [chunk['chunk_id'] for chunk in chunks if re.search(r'(?:\b(?:qui|quy)\s+tắc\s+|\brule\s+)6\b', chunk.get('content', ''), re.I)]
    if not heading or not rules: return []
    comparisons = []
    plastic_profile = {**profile, 'decorative_finish': False, 'plastic_layer': True}
    for candidate in paper_candidates(plastic_profile, candidates):
        if len(candidate['code']) == 8 and candidate['code'].startswith('481159') and re.search(r'(?:^|→)\s*(?:-\s*)*loại khác\s*$', candidate.get('description', ''), re.I):
            comparisons.append({'code': candidate['code'], 'reason': 'Dễ nhầm vì cùng là giấy có lớp phủ. Nhánh này dành cho giấy tráng, thấm tẩm hoặc phủ bằng plastic; tên PU riêng lẻ không xác nhận giấy ghép/phủ màng plastic. Mô tả đã khai được đối chiếu theo giấy trang trí xử lý bề mặt dùng dán lên ván.', 'source_chunk_ids': heading[:1] + rules[:1]})
    if profile['width_cm'] is not None and profile['width_cm'] > 36:
        for candidate in candidates:
            label = candidate.get('description', '')
            if len(candidate['code']) == 8 and candidate['code'].startswith('481190') and re.search(r'không\s*quá\s*15\s*cm', label, re.I) and re.search(r'(?:^|→)\s*(?:-\s*)*loại khác\s*$', label, re.I):
                comparisons.append({'code': candidate['code'], 'reason': 'Cùng phân nhóm giấy khác nhưng nhánh danh mục áp dụng cho cuộn khổ không quá 15 cm hoặc tờ không có chiều nào trên 36 cm. Khổ đã khai ' + profile['width'] + ' vượt các giới hạn này nên không chọn nhánh kích thước nhỏ.', 'source_chunk_ids': heading[:1] + rules[:1]})
    return comparisons[:3]
