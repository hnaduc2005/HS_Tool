from app.document_normalization import searchable_text, normalized_chunk, embedding_text


def test_searchable_representation_preserves_numbers_symbols_negation_and_formulas():
    original = '— 1849 —\nMáy dệt\nkim phẳng; không hoạt động bằng điện.\n≤ 165 mm; 1,5 kW; cm³; 84.81. - Van\u00ad\u200b'
    result = searchable_text(original)
    assert 'Máy dệt kim phẳng' in result
    assert 'không hoạt động bằng điện' in result
    assert '≤ 165 mm; 1,5 kW; cm³; 84.81. - Van' in result
    assert '1849' not in result
    assert original.startswith('— 1849 —'), 'Source text must remain unchanged'


def test_stale_context_is_repaired_and_subsection_cannot_leak_to_next_heading():
    _, metadata, context = normalized_chunk('84.47 - Máy dệt.\n(C) MÁY SẢN XUẤT REN', {'hs_heading': '8445', 'file': 'legal.pdf'}, {})
    assert metadata['hs_heading'] == '8447' and context['legal_subsection'] == 'C'
    _, continuation, context = normalized_chunk('Máy dệt móc làm đồ trang trí.', {}, context)
    assert continuation['legal_subsection'] == 'C' and continuation['hs_heading'] == '8447'
    _, next_heading, _ = normalized_chunk('84.81. - Vòi, van.', {'hs_heading': '8480'}, context)
    assert next_heading['hs_heading'] == '8481'
    assert 'legal_subsection' not in next_heading


def test_heading_mentions_in_prose_do_not_overwrite_structural_context():
    _, metadata, _ = normalized_chunk('Các máy của nhóm 84.52 được loại trừ; xem Chương 85.', {}, {'hs_heading': '8447', 'hs_chapter': '84'})
    assert metadata['hs_heading'] == '8447'


def test_general_rule_context_is_carried_to_continuation_chunks():
    _, metadata, context = normalized_chunk('QUI TẮC 6\nChỉ so sánh phân nhóm cùng cấp.', {}, {})
    assert metadata['general_rule'] == '6'
    _, continuation, _ = normalized_chunk('Các chú giải phần và chương cũng áp dụng.', {}, context)
    assert continuation['general_rule'] == '6'


def test_embedding_representation_uses_normalized_text_and_explicit_context():
    text = embedding_text('máy dệt\nmóc', {'hs_heading': '8447', 'hs_chapter': '84', 'legal_subsection': 'C'})
    assert text.startswith('Chương 84; Nhóm 8447; Mục C\n')
    assert text.endswith('máy dệt móc')
