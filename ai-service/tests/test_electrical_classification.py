import asyncio
import json
import pytest
from app import rag
from app.ai_client import AIProvider
from app.electrical_classification import electrical_function, catalog_electrical_function, function_candidates, converter_scenarios, complete_converter_analysis

HEADING = 'Máy biến điện (máy biến áp và máy biến dòng), máy biến đổi điện tĩnh (ví dụ, bộ chỉnh lưu) và cuộn cảm'
CATALOG = [
    {'code': '85042199', 'description': HEADING + ' → Máy biến điện sử dụng điện môi lỏng: → Có công suất danh định không quá 650 kVA: → Loại khác: → Loại khác'},
    {'code': '85043199', 'description': HEADING + ' → Máy biến điện khác: → Có công suất danh định không quá 1 kVA: → Loại khác'},
    {'code': '85044011', 'description': HEADING + ' → Máy biến đổi tĩnh điện: → Dùng cho các máy xử lý dữ liệu tự động và các khối chức năng của chúng, và thiết bị viễn thông: → Bộ nguồn cấp điện liên tục (UPS) (SEN)'},
    {'code': '85044019', 'description': HEADING + ' → Máy biến đổi tĩnh điện: → Dùng cho các máy xử lý dữ liệu tự động và các khối chức năng của chúng, và thiết bị viễn thông: → Loại khác'},
    {'code': '85044030', 'description': HEADING + ' → Máy biến đổi tĩnh điện: → Bộ chỉnh lưu khác'},
    {'code': '85044040', 'description': HEADING + ' → Máy biến đổi tĩnh điện: → Bộ nghịch lưu'},
    {'code': '85044090', 'description': HEADING + ' → Máy biến đổi tĩnh điện: → Loại khác'},
    {'code': '85045095', 'description': HEADING + ' → Cuộn cảm khác: → Loại khác'},
    {'code': '85371099', 'description': 'Bảng, panel, tủ điều khiển điện → Dùng cho điện áp không quá 1.000 V → Loại khác'},
]
SOURCES = [
    {'chunk_id': 'r1', 'content': 'QUI TẮC 1'}, {'chunk_id': 'r6', 'content': 'RULE 6'},
    {'chunk_id': 'subheading', 'content': '85.04 - Máy biến điện, máy biến đổi điện tĩnh và cuộn cảm. 8504.40 - Máy biến đổi tĩnh điện'},
    {'chunk_id': 'definition', 'content': '(II) CÁC THIẾT BỊ BIẾN ĐỔI TĨNH ĐIỆN. Thiết bị biến đổi dòng điện và tần số nguồn xoay chiều. Thiết bị nghịch lưu DC sang AC.'},
]


def test_heading_title_does_not_prove_transformer_is_a_static_converter():
    assert catalog_electrical_function(CATALOG[0]) == 'transformer'
    assert catalog_electrical_function(CATALOG[6]) == 'static_converter'
    assert catalog_electrical_function({'code': '8504', 'description': HEADING}) is None
    eligible, excluded = function_candidates('INVERTER, MODEL: JK200A-075-4T', CATALOG)
    assert {c['code'] for c in eligible} == {'85044011', '85044019', '85044030', '85044040', '85044090'}
    assert {'85042199', '85043199', '85045095', '85371099'} <= {c['code'] for c in excluded}


@pytest.mark.parametrize('description,expected', [
    ('INVERTER, MODEL: JK200A-075-4T', ['85044090', '85044040']),
    ('VARIABLE FREQUENCY DRIVE, 75 kW', ['85044090']),
    ('Biến tần điều khiển động cơ, công suất 7,5 kW', ['85044090']),
    ('DC to AC inverter 12V/230V', ['85044040']),
    ('Bộ nghịch lưu dòng một chiều thành xoay chiều', ['85044040']),
    ('RECTIFIER, 75 kW', ['85044030']),
    ('UPS dùng cho máy tính', ['85044011']),
    ('Bộ chỉnh lưu dùng cho thiết bị viễn thông', ['85044019']),
    ('RECTIFIER, not a battery charger, not for computers or telecommunications', ['85044030']),
    ('Solar inverter', ['85044040']),
    ('DC to DC converter, industrial', ['85044090']),
    ('UPS for industrial equipment, not for computers', ['85044090']),
])
def test_converter_scenarios_follow_function_before_other_suffix(description, expected):
    assert [o['code'] for o in converter_scenarios(description, CATALOG)] == expected


@pytest.mark.parametrize('description', [
    'INVERTER AIR CONDITIONER', 'Máy giặt công nghệ biến tần',
    'Control cabinet with inverter', 'PCB for inverter', 'Rotary frequency converter',
])
def test_inverter_component_does_not_classify_a_whole_appliance_or_part(description):
    assert electrical_function(description) is None


def test_transformer_and_inductor_remain_in_their_own_function_branches():
    assert {c['code'] for c in function_candidates('OIL IMMERSED TRANSFORMER 500 kVA', CATALOG)[0]} == {'85042199'}
    assert {c['code'] for c in function_candidates('DRY TYPE TRANSFORMER 500 kVA, not an inverter', CATALOG)[0]} == {'85043199'}
    assert {c['code'] for c in function_candidates('INDUCTOR 10 A', CATALOG)[0]} == {'85045095'}


def test_converter_completion_replaces_contradictory_code_and_legal_steps():
    bad = {'status': 'CONDITIONAL', 'catalog_hints': {'heading_hints': ['85042199']}, 'missing_information': ['Thiếu kVA và điện môi'],
           'legal_analysis': {'legal_steps': [{'rule': 'Quy tắc 6', 'application': 'Chọn 850421 vì máy biến đổi điện tĩnh', 'source_chunk_ids': ['subheading']}],
                              'hypotheses': [{'code': '85042199', 'assumptions': ['Thiết bị là máy biến đổi điện tĩnh']}]}}
    options = converter_scenarios('INVERTER, MODEL: JK200A-075-4T', CATALOG)
    result = complete_converter_analysis(bad, 'INVERTER, MODEL: JK200A-075-4T', options, SOURCES)
    assert result['legal_analysis']['hypotheses'][0]['code'] == '85044090'
    assert all('850421' not in step['application'] for step in result['legal_analysis']['legal_steps'])
    assert all('definition' in h['source_chunk_ids'] for h in result['legal_analysis']['hypotheses'])
    assert 'catalog_hints' not in result
    assert not result['missing_information']
    assert not complete_converter_analysis({}, 'INVERTER', options, SOURCES[:3]), 'A heading title alone is not technical evidence'


def test_declared_conversion_is_not_repeated_as_an_assumption():
    options = converter_scenarios('Biến tần, công suất 7,5 kW', CATALOG)
    assert len(options) == 1
    assert {a['attribute'] for a in options[0]['assumed_attributes']} == {'use'}
    assert not any('tần số' in assumption for assumption in options[0]['assumptions'])


@pytest.mark.parametrize('description,code', [
    ('Biến tần dùng điều khiển động cơ, công suất 7,5 kW', '85044090'),
    ('RECTIFIER, not a battery charger, not for computers or telecommunications', '85044030'),
])
def test_fully_declared_converter_has_no_physical_assumptions(description, code):
    options = converter_scenarios(description, CATALOG)
    result = complete_converter_analysis({}, description, options, SOURCES)
    assert result['status'] == 'COMPLETED' and result['recommended_code'] == code
    assert not result['legal_analysis']['hypotheses'] and not result['legal_analysis']['limitations']
    assert not result['missing_information']
    assert not any('giả định' in item['answer'].casefold() for item in result['legal_analysis']['decision_questions'])


@pytest.mark.parametrize('description,status', [
    ('Biến tần dùng điều khiển động cơ, công suất 7,5 kW', 'COMPLETED'),
    ('Biến tần, công suất 7,5 kW', 'CONDITIONAL'),
])
def test_entire_converter_flow_uses_only_the_missing_suffix_conditions(monkeypatch, description, status):
    class Provider(AIProvider):
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            if 'product_understanding' not in json.loads(messages[1]['content']):
                return json.dumps({'identity_eligible_codes': ['85044090'], 'missing_attributes': ['power', 'material']})
            return json.dumps({'status': 'INSUFFICIENT_EVIDENCE', 'legal_analysis': {'hypotheses': []}})
    async def retrieve(*args):
        return [{'id': source['chunk_id'], 'document_id': 'doc', 'page': 1, 'title': 'Chú giải',
            'semantic_score': .8, 'keyword_score': .5, 'rerank_score': .8, 'content': source['content']} for source in SOURCES]
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify(description, CATALOG, Provider()))
    assert result['status'] == status
    if status == 'COMPLETED':
        assert result['recommended_code'] == '85044090' and not result['legal_analysis']['hypotheses']
        assert not result['legal_analysis']['product_understanding']['missing_attributes']
    else:
        hypotheses = result['legal_analysis']['hypotheses']
        assert hypotheses and all({a['attribute'] for a in h['assumed_attributes']} == {'use'} for h in hypotheses)
        assert not any('7,5' in assumption or 'tần số' in assumption for h in hypotheses for assumption in h['assumptions'])


def test_provider_and_rag_reject_wrong_function_even_with_real_citations(monkeypatch):
    class Provider(AIProvider):
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            context = json.loads(messages[1]['content'])
            assert all(c['code'].startswith('850440') for c in context['candidates'])
            # Deliberately reproduce the user's failure despite a valid source ID.
            return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                {'code': '85042199', 'assumptions': ['Bộ biến đổi điện tĩnh'], 'reasoning': '8504 mô tả biến đổi điện', 'source_chunk_ids': ['subheading']}]}})
    async def retrieve(*_args):
        return [{'id': c['chunk_id'], 'document_id': 'doc-1', 'page': 1, 'title': 'Chú giải',
                 'semantic_score': .9, 'keyword_score': .5, 'rerank_score': .9, 'content': c['content']} for c in SOURCES]
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify('INVERTER, MODEL: JK200A-075-4T', CATALOG, Provider()))
    assert result['status'] == 'CONDITIONAL'
    assert result['normalized_product']['provisional_code'] == '85044090'
    assert [h['code'] for h in result['legal_analysis']['hypotheses']] == ['85044090', '85044040']


def test_inverter_catalog_gap_requests_function_search_not_wrong_transformer(monkeypatch):
    class Provider:
        async def classifyProduct(self, description, candidates, chunks):
            assert not candidates
            return {'status': 'COMPLETED', 'recommended_code': '85042199', 'source_chunk_ids': ['definition']}
    async def retrieve(*_args):
        return [{'id': 'definition', 'document_id': 'doc-1', 'page': 1, 'title': 'Chú giải',
                 'semantic_score': .9, 'keyword_score': .5, 'rerank_score': .9, 'content': SOURCES[3]['content']}]
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify('INVERTER', CATALOG[:2], Provider()))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['catalog_hints'] == {'queries': ['máy biến đổi tĩnh điện'], 'heading_hints': []}
    assert not result['normalized_product'].get('provisional_code')
