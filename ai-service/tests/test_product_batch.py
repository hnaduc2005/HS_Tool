import asyncio
from pathlib import Path
from app.product_batch import checked_batch, invoice_segments, prepare_batch


def test_independent_goods_keep_all_multiline_specs_and_order():
    first = '1. COMPUTERIZED CROCHET MACHINE\nMODEL: B16 20\nPOWER: 1.5KW'
    second = '2. INVERTER, MODEL: JK200A-075-4T'
    result = checked_batch(first + '\n\n' + second, {'segments': [
        {'kind': 'item', 'text': first}, {'kind': 'item', 'text': second}]})
    assert not result['needs_review']
    assert result['items'] == [{'description': first[3:]}, {'description': second[3:]}]


def test_single_machine_and_gift_set_are_preserved_verbatim():
    for text in ['COMPUTERIZED CROCHET MACHINE\nMODEL: B16 20\nPOWER: 1.5KW',
                 'Bộ quà tặng gồm caravat và vớ']:
        assert checked_batch(text, {'segments': [{'kind': 'item', 'text': text}]}) == {
            'items': [{'description': text}], 'needs_review': False, 'message': ''}


def test_explicit_shared_statement_applies_to_each_good():
    first, second, common = 'Máy bơm nước, model A.', 'Van khí nén, model B.', 'Tất cả hàng mới 100%.'
    result = checked_batch('\n'.join([first, second, common]), {'segments': [
        {'kind': 'item', 'text': first}, {'kind': 'item', 'text': second}, {'kind': 'shared', 'text': common}]})
    assert result['items'] == [{'description': first + '\n' + common}, {'description': second + '\n' + common}]


def test_omitted_or_invented_specs_require_review_without_losing_original():
    text = 'Máy bơm nước 5kW\nVan khí nén model B'
    for segments in [
        [{'kind': 'item', 'text': 'Máy bơm nước'}, {'kind': 'item', 'text': 'Van khí nén model B'}],
        [{'kind': 'item', 'text': 'Máy bơm nước 7kW'}, {'kind': 'item', 'text': 'Van khí nén model B'}],
        [{'kind': 'shared', 'text': text}],
    ]:
        result = checked_batch(text, {'segments': segments})
        assert result['needs_review'] and result['items'] == [{'description': text}]


def test_repeated_goods_remain_independent_and_more_than_ten_require_review():
    text = 'INVERTER MODEL A'
    result = checked_batch(text + '\n' + text, {'segments': [{'kind': 'item', 'text': text}] * 2})
    assert len(result['items']) == 2 and not result['needs_review']
    result = checked_batch('\n'.join([text] * 11), {'segments': [{'kind': 'item', 'text': text}] * 11})
    assert result['needs_review']


def test_oversize_item_is_not_truncated_or_submitted_as_valid():
    text = 'Máy bơm nước ' + 'a' * 2100
    result = checked_batch(text, {'segments': [{'kind': 'item', 'text': text}]})
    assert result['needs_review'] and result['items'][0]['description'] == text


def test_short_independent_goods_are_not_rejected_for_missing_details():
    result = checked_batch('Cà vạt\nVớ', {'segments': [
        {'kind': 'item', 'text': 'Cà vạt'}, {'kind': 'item', 'text': 'Vớ'}]})
    assert not result['needs_review'] and len(result['items']) == 2


def test_one_products_model_cannot_be_reassigned_as_shared_data():
    first, spec, second = 'Máy bơm nước', 'Model: PU-500', 'Van khí nén'
    text = '\n'.join([first, spec, second])
    result = checked_batch(text, {'segments': [
        {'kind': 'item', 'text': first}, {'kind': 'shared', 'text': spec}, {'kind': 'item', 'text': second}]})
    assert result['needs_review'] and result['items'][0]['description'] == text


def test_model_reports_oversize_list_without_collapsing_it_into_one_classification():
    text = '\n'.join(['INVERTER MODEL A'] * 11)
    result = checked_batch(text, {'too_many_items': True, 'segments': [{'kind': 'item', 'text': text}]})
    assert result['needs_review'] and '10' in result['message']
    assert result['items'][0]['description'] == text


class NoChat:
    async def chat_json(self, *_):
        raise AssertionError('Explicit invoice rows must not depend on a model response')


def test_ten_user_invoice_rows_remain_ten_with_all_models_and_money():
    text = (Path(__file__).parent / 'fixtures/invoice-ten-products.txt').read_text(encoding='utf-8').strip()
    result = asyncio.run(prepare_batch(text, NoChat()))
    assert not result['needs_review'] and len(result['items']) == 10
    expected = ['JK200A-055-4T', 'JK200A-075-4T', 'JK200A-090-4T', 'JK200A-110-4T',
                'TVF225M-8-45-152 WT', 'TVF225M-8-55-152 WT', 'TVF250M-8-75-152 WT',
                'TVF225M-8-75-152 WT-S1700', 'TVF280M-8-90-152 WT', 'TVF280M-8-110-152 WT']
    for index, item in enumerate(result['items']):
        assert expected[index] in item['description']
        for other in expected:
            if other != expected[index]:
                assert other not in item['description']
    assert result['items'][0]['description'].endswith('2 SET 1,245.00 2,490.00')
    assert result['items'][7]['description'].endswith('2 PCS 3,179.00 6,358.00')
    assert 'MAGNET\nSYNCHRONOUS' in result['items'][4]['description']
    assert text == '\n\n'.join(f'{index + 1}. {item["description"]}' for index, item in enumerate(result['items']))


def test_invoice_numbering_handles_crlf_parentheses_and_no_blank_lines():
    text = '1) INVERTER, MODEL: A\r\n2) SERVO MOTOR, MODEL:\r\nB WT\r\n2 PCS 100.00 200.00'
    result = asyncio.run(prepare_batch(text, NoChat()))
    assert len(result['items']) == 2 and not result['needs_review']
    assert 'B WT\r\n2 PCS' in result['items'][1]['description']


def test_same_model_on_different_invoice_rows_is_not_deduplicated():
    text = '1. INVERTER, MODEL: A\n\n2. INVERTER, MODEL: A'
    result = asyncio.run(prepare_batch(text, NoChat()))
    assert len(result['items']) == 2 and result['items'][0] == result['items'][1]


def test_numbered_components_specifications_and_unscoped_shared_facts_use_semantic_path():
    for text in [
        'Bộ quà tặng gồm:\n1. Cà vạt model A\n2. Vớ model B',
        '1. COMPUTERIZED CROCHET MACHINE, MODEL: A\n2. POWER: 1.5KW\n3. MODEL: B16 20',
        '1. Bộ dụng cụ MODEL: A\n2. Phụ kiện đi kèm MODEL: B',
        '1. Máy bơm MODEL: A\n2. Van MODEL: B\nTất cả hàng mới 100%',
        '1. Gạo 55%\n2. Tôm 11%',
    ]:
        assert invoice_segments(text) is None


def test_eleven_explicit_invoice_rows_require_review_and_keep_every_row():
    text = '\n'.join(f'{index}. INVERTER, MODEL: A-{index}' for index in range(1, 12))
    result = asyncio.run(prepare_batch(text, NoChat()))
    assert result['needs_review'] and result['items'][0]['description'] == text
