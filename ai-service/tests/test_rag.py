import asyncio
import pytest
from app import rag


def test_valve_parent_branches_survive_cap_and_wrong_reasoning_is_rejected(monkeypatch):
    from test_catalog_conditions import CATALOG
    from app.catalog_conditions import valve_scenarios
    async def fake_retrieve(*_args):
        return [{'id': 'valves', 'document_id': 'doc-1', 'content': '84.81. - Vòi, van. 8481.20 - Van truyền động khí nén.',
                 'page': 1951, 'title': 'Chú giải HS', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .9}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            assert {'84812011', '84812019', '84812090'} <= {c['code'] for c in candidates}
            option = valve_scenarios(description, candidates)[0]
            return {'status': 'CONDITIONAL', 'legal_analysis': {'legal_steps': [
                {'rule': 'Quy tắc 6', 'application': 'Xét nhánh cha và nhánh con.', 'source_chunk_ids': ['valves']}],
                'hypotheses': [{'code': '84812019', 'assumptions': ['Đường kính phù hợp'], 'reasoning': 'Chọn theo kích thước', 'source_chunk_ids': ['valves']},
                    {'code': option['code'], 'assumptions': option['assumptions'], 'reasoning': 'Không thuộc nhánh van cổng vận hành tay.', 'source_chunk_ids': ['valves']}]}}
    candidates = [{'code': f'848110{i:02d}', 'description': 'Van giảm áp', 'score': .99} for i in range(35)] + CATALOG
    result = asyncio.run(rag.classify('PNEUMATIC VALVE φ350', candidates, Provider()))
    assert result['status'] == 'CONDITIONAL'
    assert result['normalized_product']['provisional_code'] == '84812090'
    assert [h['code'] for h in result['legal_analysis']['hypotheses']] == ['84812090']

FOOD_HYPOTHESES = [
    {'code': '16052990', 'label': 'Phần còn lại không làm đổi ưu thế của tôm',
     'assumptions': ['10% còn lại là dầu, nước hoặc nguyên liệu không thuộc Chương 16'],
     'reasoning': 'Tôm 11% + thịt lợn 10% = 21%; tôm lớn hơn thịt lợn. Hộp kín khí, cơm chiên không phải tôm viên hoặc tôm tẩm bột.', 'source_chunk_ids': ['legal-1']},
    {'code': '16024991', 'label': 'Phần còn lại có thêm thịt lợn',
     'assumptions': ['10% còn lại là thịt lợn', 'Hộp kín khí để bán lẻ'],
     'reasoning': 'Thịt lợn 10% + 10% = 20%, lớn hơn tôm 11%; xét 16.02, loại khác không phải thịt nguội và đóng bao bì kín khí để bán lẻ.', 'source_chunk_ids': ['legal-1']},
]

PRODUCTS = [
    ('Áo thun cotton dệt kim cho nam dùng mặc hàng ngày', '61091010'),
    ('Giày thể thao mũ dệt đế cao su dành cho người lớn', '64041190'),
    ('Máy lọc nước gia đình công nghệ RO để uống hàng ngày', '84212111'),
    ('Điện thoại thông minh có kết nối mạng di động 5G', '85171300'),
    ('Bàn làm việc bằng gỗ sử dụng trong văn phòng', '94033000'),
]

class FakeProvider:
    def __init__(self, code, cite=True): self.code, self.cite = code, cite
    async def classifyProduct(self, description, candidates, chunks):
        ids = [chunks[0]['chunk_id']] if self.cite else []
        return {'status': 'COMPLETED', 'recommended_code': self.code, 'reasoning': 'Ví dụ thử nghiệm', 'llm_score': 1, 'alternatives': [], 'source_chunk_ids': ids,
                'legal_analysis': {'summary': 'Đối chiếu mô tả hàng hóa', 'product_facts': [description],
                    'legal_steps': [{'rule': f'Danh mục mô tả mã {self.code}', 'application': f'Đặc tính hàng phù hợp mô tả mã {self.code}', 'source_chunk_ids': ids}],
                    'alternatives': [], 'conclusion': f'Đề xuất {self.code}', 'limitations': []}}

@pytest.mark.parametrize('description,code', PRODUCTS)
def test_ten_demo_products_require_candidate_and_citation(monkeypatch, description, code):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chunk-1', 'document_id': 'doc-1', 'content': f'{description}. Mã ứng viên {code}.', 'page': 2, 'title': 'DEMO DATA', 'semantic_score': .95, 'keyword_score': .9, 'rerank_score': .94}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify(description, [{'code': code, 'description': description}], FakeProvider(code)))
    assert result['status'] == 'COMPLETED'
    assert result['recommended_code'] == code
    assert result['sources'][0]['page'] == 2
    assert result['legal_analysis']['legal_steps'][0]['source_chunk_ids'] == ['chunk-1']

def test_rejects_invented_code(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chunk-1', 'document_id': 'doc-1', 'content': query, 'page': 1, 'title': 'DEMO DATA', 'semantic_score': 1, 'keyword_score': 1, 'rerank_score': 1}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Áo thun nam bằng cotton dệt kim', [{'code': '61091010', 'description': 'Áo thun nam bằng cotton dệt kim'}], FakeProvider('99999999')))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'


def test_accepts_dotted_format_for_an_existing_candidate(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chunk-1', 'document_id': 'doc-1', 'content': '9403.60.90 - Đồ nội thất bằng gỗ khác, loại khác.',
                 'page': 1, 'title': 'Danh mục HS', 'semantic_score': .95, 'keyword_score': .9, 'rerank_score': .95}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Bàn ăn bằng gỗ dùng trong phòng ăn',
                                      [{'code': '94036090', 'description': 'Đồ nội thất bằng gỗ khác, loại khác'}],
                                      FakeProvider('9403.60.90')))
    assert result['status'] == 'COMPLETED'
    assert result['recommended_code'] == '94036090'


def test_six_digit_parent_is_not_a_completed_vietnamese_code(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chapter-94', 'document_id': 'doc-1', 'content': '9403.60 - Đồ nội thất bằng gỗ khác.',
                 'page': 2344, 'title': 'Danh mục HS', 'semantic_score': .95, 'keyword_score': .9, 'rerank_score': .95}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    candidates = [
        {'code': '940360', 'description': 'Đồ nội thất bằng gỗ khác', 'score': .95},
        {'code': '94036010', 'description': 'Tủ hút hơi độc', 'score': .92},
        {'code': '94036090', 'description': 'Loại khác', 'score': .92},
    ]
    class ParentProvider(FakeProvider):
        async def classifyProduct(self, description, ranked, chunks):
            assert {item['code'] for item in ranked} == {'94036010', '94036090'}
            return await super().classifyProduct(description, ranked, chunks)
    result = asyncio.run(rag.classify('Kệ TV bằng gỗ ghép và ván MDF', candidates, ParentProvider('940360')))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert any('8 số' in item for item in result['missing_information'])


def test_guided_six_digit_source_supports_verified_eight_digit_candidate(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chapter-94', 'document_id': 'doc-1', 'content': '9403.60 - Đồ nội thất bằng gỗ khác.',
                 'page': 2344, 'title': 'Chú giải HS', 'semantic_score': 0, 'keyword_score': .1, 'rerank_score': .65}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Bàn ăn bằng gỗ dùng trong phòng ăn',
                                      [{'code': '94036090', 'description': 'Đồ nội thất bằng gỗ khác, loại khác'}],
                                      FakeProvider('94036090')))
    assert result['status'] == 'COMPLETED'
    assert result['recommended_code'] == '94036090'

def test_rejects_uncited_result(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'chunk-1', 'document_id': 'doc-1', 'content': query, 'page': 1, 'title': 'DEMO DATA', 'semantic_score': 1, 'keyword_score': 1, 'rerank_score': 1}]
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Áo thun nam bằng cotton dệt kim', [{'code': '61091010', 'description': 'Áo thun nam bằng cotton dệt kim'}], FakeProvider('61091010', cite=False)))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['legal_analysis']['legal_steps'] == []
    assert result['legal_analysis']['limitations']


def test_insufficient_result_keeps_verified_legal_steps_and_sources(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'legal-1', 'document_id': 'doc-1', 'content': 'Chú giải 2 Chương 16: trên 20% thịt hoặc tôm.', 'page': 76,
                 'title': 'Nghị định 26/2023', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .8}]
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            return {'status': 'INSUFFICIENT_EVIDENCE', 'recommended_code': None, 'missing_information': ['Thiếu 10% thành phần'],
                    'legal_analysis': {'summary': 'Tổng phần đã khai là 90%.', 'product_facts': ['Tôm 11%, thịt lợn 10%'],
                        'legal_steps': [{'rule': 'Chú giải 2 Chương 16', 'application': 'Phần động vật đã khai là 21%.', 'source_chunk_ids': ['legal-1', 'invented']}],
                        'alternatives': [], 'conclusion': 'Chưa thể chốt mã tám số.', 'limitations': ['Thiếu 10% thành phần']}}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%',
                                      [{'code': '16052990', 'description': 'Tôm chế biến, loại khác'}], Provider()))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['sources'][0]['chunk_id'] == 'legal-1'
    assert result['legal_analysis']['legal_steps'][0]['source_chunk_ids'] == ['legal-1']


def test_incomplete_recipe_cannot_be_marked_completed(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'legal-1', 'document_id': 'doc-1', 'content': 'Chú giải 2 Chương 16: trên 20% thịt hoặc tôm; mã 16052990.', 'page': 76,
                 'title': 'Nghị định 26/2023', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .8}]
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            return {'status': 'COMPLETED', 'recommended_code': '16052990', 'reasoning': 'Tôm nhiều hơn thịt', 'llm_score': 1,
                    'source_chunk_ids': ['legal-1'], 'legal_analysis': {'summary': 'Tôm 11%, thịt 10%.', 'product_facts': [],
                        'legal_steps': [{'rule': 'Chú giải 2 Chương 16', 'application': '21% vượt 20%.', 'source_chunk_ids': ['legal-1']}],
                        'alternatives': [], 'hypotheses': FOOD_HYPOTHESES, 'conclusion': 'Mã 16052990', 'limitations': []}}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%',
                                      [{'code': '16052990', 'description': 'Tôm chế biến, loại khác'}, {'code': '16024991', 'description': 'Chế phẩm thịt lợn, loại khác, hộp kín khí để bán lẻ'}], Provider()))
    assert result['status'] == 'CONDITIONAL'
    assert result['normalized_product']['provisional_code'] == '16052990'
    assert 'có điều kiện' in result['legal_analysis']['conclusion']
    assert {item['code'] for item in result['legal_analysis']['hypotheses']} == {'16052990', '16024991'}


def test_mixed_food_keeps_chapter_16_candidate_and_explains_missing_ten_percent(monkeypatch):
    seen = []
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'legal-1', 'document_id': 'doc-1', 'content': 'Chú giải 2 Chương 16: trên 20% thịt và tôm. 1605.29.90 loại khác.', 'page': 76, 'title': 'Nghị định 26/2023', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .8}]
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            seen.extend(item['code'] for item in candidates)
            return {'status': 'INSUFFICIENT_EVIDENCE', 'missing_information': ['Cần làm rõ thành phần'],
                    'legal_analysis': {'hypotheses': FOOD_HYPOTHESES[:1]}}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    candidates = [{'code': str(10000000 + number), 'description': 'Hàng khác', 'score': .1} for number in range(20)]
    candidates.append({'code': '16052990', 'description': 'Tôm chế biến → Loại khác', 'score': .9})
    description = 'Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%'
    result = asyncio.run(rag.classify(description, candidates, Provider()))
    assert '16052990' in seen
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['normalized_product']['provisional_code'] == '16052990'
    assert '16052990' in result['legal_analysis']['conclusion']
    assert any('10% còn lại' in note for note in result['missing_information'])


def test_hypotheses_require_eight_digit_catalog_code_assumptions_and_citation():
    entries = FOOD_HYPOTHESES + [
        {**FOOD_HYPOTHESES[0], 'code': '160529'},
        {**FOOD_HYPOTHESES[0], 'code': '99999999'},
        {**FOOD_HYPOTHESES[0], 'assumptions': []},
        {**FOOD_HYPOTHESES[0], 'source_chunk_ids': ['invented']},
    ]
    analysis = rag.legal_analysis({'legal_analysis': {'hypotheses': entries}}, 'Cơm chiên',
                                [{'id': 'legal-1'}], {'16052990', '16024991'}, [])
    assert len(analysis['hypotheses']) == 2
    assert analysis['hypotheses'][0]['code'] == '16052990'


def test_catalog_recovery_prioritizes_proposed_codes_and_keeps_both_branches():
    hints = rag.catalog_recovery_hints({
        'recommended_code': '1605.29.90',
        'catalog_hints': {'heading_hints': ['1904', '1602', '1605', '2106'], 'queries': ['thịt lợn đã chế biến']},
        'legal_analysis': {'hypotheses': FOOD_HYPOTHESES},
    }, {'16024991'})
    assert hints['heading_hints'][:2] == ['16052990', '16024991']
    assert hints['queries'] == ['thịt lợn đã chế biến']


def test_missing_gift_material_returns_conditional_codes_and_self_answered_questions(monkeypatch):
    async def fake_retrieve(*_args):
        return [{'id': 'rule-3', 'document_id': 'doc-1', 'content': 'Quy tắc 1, 3 và 6; các mặt hàng phân loại riêng khi không đáp ứng điều kiện bộ bán lẻ.',
                 'page': 8, 'title': 'Quy tắc', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .9}]
    class Provider:
        async def classifyProduct(self, *_args):
            return {'status': 'CONDITIONAL', 'missing_information': ['Chất liệu chưa được khai'], 'legal_analysis': {
                'summary': 'Chưa đủ căn cứ để xác định một mã duy nhất.',
                'decision_questions': [{'question': 'Bộ có đáp ứng điều kiện bán lẻ không?', 'answer': 'Giả định không đáp ứng: phân loại riêng từng món.', 'source_chunk_ids': ['rule-3', 'invented']}],
                'legal_steps': [{'rule': 'Quy tắc 1', 'application': 'Phân loại riêng từng mặt hàng.', 'source_chunk_ids': ['rule-3']}],
                'hypotheses': [{'code': '62152090', 'label': 'Cà vạt polyester và vớ cotton, phân loại riêng', 'classification_mode': 'separate',
                    'assumptions': ['Cà vạt bằng polyester dệt thoi, không in batik', 'Vớ cotton dệt kim thông thường', 'Hai món không tạo thành bộ bán lẻ theo quy tắc'],
                    'reasoning': 'Phân loại từng món theo chất liệu giả định và mô tả nhóm.', 'source_chunk_ids': ['rule-3'],
                    'items': [{'name': 'Cà vạt', 'code': '62152090', 'source_chunk_ids': ['rule-3']},
                              {'name': 'Vớ', 'code': '61159500', 'source_chunk_ids': ['rule-3']}]}]}}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify('Bộ quà tặng gồm caravat và vớ', [
        {'code': '62152090', 'description': 'Cà vạt sợi nhân tạo, loại khác'},
        {'code': '61159500', 'description': 'Bít tất dệt kim từ bông, loại khác'},
    ], Provider()))
    assert result['status'] == 'CONDITIONAL'
    assert result['normalized_product']['provisional_codes'] == ['62152090', '61159500']
    assert 'provisional_code' not in result['normalized_product']
    assert 'chưa đủ' not in result['legal_analysis']['summary'].lower()
    assert '61159500' in result['legal_analysis']['conclusion']
    assert result['legal_analysis']['decision_questions'][0]['source_chunk_ids'] == ['rule-3']


@pytest.mark.parametrize('invalid_item', [
    {'name': 'Vớ', 'code': '99999999', 'source_chunk_ids': ['rule-3']},
    {'name': 'Vớ', 'code': '61159500', 'source_chunk_ids': ['invented']},
])
def test_separate_classification_cannot_silently_drop_an_unverified_item(invalid_item):
    hypothesis = {'code': '62152090', 'classification_mode': 'separate', 'assumptions': ['Cà vạt polyester, vớ cotton'],
                  'reasoning': 'Phân loại riêng', 'source_chunk_ids': ['rule-3'],
                  'items': [{'name': 'Cà vạt', 'code': '62152090', 'source_chunk_ids': ['rule-3']}, invalid_item]}
    analysis = rag.legal_analysis({'legal_analysis': {'hypotheses': [hypothesis]}}, 'Bộ cà vạt và vớ', [{'id': 'rule-3'}], {'62152090', '61159500'}, [])
    assert analysis['hypotheses'] == []


def test_candidate_selection_keeps_common_materials_and_ordinary_suffix(monkeypatch):
    async def fake_retrieve(*_args):
        return [{'id': 'rule-3', 'document_id': 'doc-1', 'content': 'Quy tắc 3', 'page': 8, 'title': 'Quy tắc',
                 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .9}]
    class Provider:
        async def classifyProduct(self, _description, candidates, _chunks):
            codes = {item['code'] for item in candidates}
            assert {'62151090', '62152090', '61159500', '61159600'} <= codes
            return {'status': 'INSUFFICIENT_EVIDENCE'}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    candidates = [{'code': f'621510{index:02d}', 'description': 'Cà vạt tơ tằm được in batik', 'score': .99} for index in range(30)]
    candidates += [{'code': '62151090', 'description': 'Cà vạt tơ tằm, loại khác', 'score': .7},
                   {'code': '62152090', 'description': 'Cà vạt sợi nhân tạo, loại khác', 'score': .7},
                   {'code': '61159500', 'description': 'Vớ từ bông', 'score': .7},
                   {'code': '61159600', 'description': 'Vớ sợi tổng hợp', 'score': .7}]
    asyncio.run(rag.classify('Bộ quà tặng gồm caravat và vớ', candidates, Provider()))


def test_candidate_ranking_keeps_a_lower_scored_competing_heading(monkeypatch):
    async def fake_retrieve(query, provider, candidates=None):
        return [{'id': 'legal-1', 'document_id': 'doc-1', 'content': 'Chú giải 2 Chương 16',
                 'page': 1, 'title': 'Nguồn thử', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .8}]
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            assert '16024991' in {item['code'] for item in candidates}
            return {'status': 'INSUFFICIENT_EVIDENCE'}
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    candidates = [{'code': str(16050000 + index), 'description': 'Hàng tôm', 'score': .95} for index in range(30)]
    candidates.append({'code': '16024991', 'description': 'Chế phẩm thịt lợn', 'score': .7})
    asyncio.run(rag.classify('Cơm chiên có tôm và thịt lợn, chưa nêu đầy đủ tỷ lệ', candidates, Provider()))


def test_numeric_power_branches_survive_many_siblings_and_cannot_be_marked_confirmed(monkeypatch):
    description = 'HIGH EFFICIENCY PERMANENT MAGNET SYNCHRONOUS SERVO MOTOR, MODEL: TVF225M-8-45-152'
    async def fake_retrieve(*_args):
        return [{'id': 'motor-source', 'document_id': 'doc-1', 'content': '85.01 động cơ điện; 8501.52 công suất trên 750 W nhưng không quá 75 kW.',
                 'page': 1978, 'title': 'Chú giải', 'semantic_score': .9, 'keyword_score': .8, 'rerank_score': .9}]
    class Provider:
        async def classifyProduct(self, _description, candidates, _chunks):
            assert {'85015229', '85015239'} <= {candidate['code'] for candidate in candidates}
            return {'status': 'COMPLETED', 'recommended_code': '85015239', 'source_chunk_ids': ['motor-source'], 'legal_analysis': {
                'product_facts': ['Công suất 45 kW'],
                'legal_steps': [{'rule': 'Quy tắc 6', 'application': 'Chọn phân nhóm theo công suất.', 'source_chunk_ids': ['motor-source']}],
                'hypotheses': [{'code': '85015239', 'assumptions': ['Giả định công suất 45 kW, AC đa pha dùng trong công nghiệp'],
                    'reasoning': '45 kW trên 37,5 kW nhưng không quá 75 kW.', 'source_chunk_ids': ['motor-source']}],
            }}
    candidates = [{'code': f'850152{index:02d}', 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất không quá 1 kW: → Loại chuyên dùng', 'score': .99}
                  for index in range(1, 26)]
    candidates.extend([
        {'code': '85015229', 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất trên 1 kW nhưng không quá 37,5 kW: → Loại khác', 'score': .7},
        {'code': '85015239', 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất trên 37,5 kW nhưng không quá 75 kW: → Loại khác', 'score': .7},
    ])
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    result = asyncio.run(rag.classify(description, candidates, Provider()))
    assert result['status'] == 'CONDITIONAL'
    assert result['normalized_product']['provisional_code'] == '85015239'
    assert result['legal_analysis']['product_facts'] == [description]
