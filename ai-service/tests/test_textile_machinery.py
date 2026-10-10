import asyncio
import json
import pytest
from app import rag
from app.ai_client import AIProvider
from app.function_classification import product_function, function_candidates
from app.textile_machinery import textile_scenarios, complete_textile_analysis, matching_textile_hypothesis
from app.legal_text import contains_phrase, phrase_search_pattern


HEADING = 'Máy dệt kim, máy khâu đính và máy tạo sợi quấn, sản xuất vải tuyn, ren, thêu, trang trí, dây tết hoặc lưới và máy tạo búi'
CATALOG = [
    {'code': '84471100', 'description': HEADING + ' → Máy dệt kim tròn: → Có đường kính trục cuốn không quá 165 mm'},
    {'code': '84471200', 'description': HEADING + ' → Máy dệt kim tròn: → Có đường kính trục cuốn trên 165 mm'},
    {'code': '84472010', 'description': HEADING + ' → Máy dệt kim phẳng; máy khâu đính: → Hoạt động bằng điện'},
    {'code': '84472020', 'description': HEADING + ' → Máy dệt kim phẳng; máy khâu đính: → Không hoạt động bằng điện'},
    {'code': '84479010', 'description': HEADING + ' → Loại khác: → Hoạt động bằng điện'},
    {'code': '84479020', 'description': HEADING + ' → Loại khác: → Không hoạt động bằng điện'},
    {'code': '84522900', 'description': 'Máy khâu → Loại khác'},
]
DESCRIPTION = 'COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW\n230011002000MM'
SOURCES = [
    {'chunk_id': 'r1', 'content': 'QUI TẮC 1'}, {'chunk_id': 'r6', 'content': 'RULE 6'},
    {'chunk_id': 'heading', 'content': '84.47 - Máy dệt kim. 8447.11 - Không quá 165mm. 8447.12 - Trên 165mm. 8447.20 - Máy dệt kim phẳng; máy khâu đính. 8447.90 - Loại khác.'},
    {'chunk_id': 'crochet', 'content': '(7) Máy sản xuất đồ trang trí bằng cách tết các sợi dệt (máy dệt viền, máy dệt móc).'},
    {'chunk_id': 'flat', 'content': 'Máy dệt kim phẳng bao gồm máy dệt kim thông thường và máy dệt kim sợi dọc (Raschel, milanese, locknit).'},
    {'chunk_id': 'circular', 'content': '(1) Máy dệt kim tròn dùng để sản xuất vải hình ống.'},
    {'chunk_id': 'stitch', 'content': '(B) MÁY KHÂU ĐÍNH sản xuất vải bằng quy trình khâu dây chuyền.'},
    {'chunk_id': 'embroidery', 'content': '(5) Máy thêu nhờ các kim khâu thêu các mẫu khác nhau trên một nền vải.'},
    {'chunk_id': 'tufting', 'content': '(9) Máy tết dùng để chèn các vòng hoặc các chùm sợi dệt ở mặt sau của vải.'},
]


@pytest.mark.parametrize('description,codes', [
    (DESCRIPTION, ['84479010']),
    ('CROCHET MACHINE making lace, POWER: 1.5 kW', ['84479010']),
    ('CROCHET MACHINE making ornamental braid, non-electric', ['84479020']),
    ('CROCHET MACHINE making ornamental braid', ['84479010', '84479020']),
    ('FLAT KNITTING MACHINE, POWER: 1.5 kW', ['84472010']),
    ('CROCHET WARP KNITTING MACHINE, electric drive', ['84472010']),
    ('STITCH-BONDING MACHINE, electric drive', ['84472010']),
    ('EMBROIDERY MACHINE, electric drive', ['84479010']),
    ('BRAIDING MACHINE, electric drive', ['84479010']),
    ('TUFTING MACHINE, electric drive', ['84479010']),
    ('CIRCULAR KNITTING MACHINE, cylinder diameter: 165 mm', ['84471100']),
    ('CIRCULAR KNITTING MACHINE, cylinder diameter: 16.6 cm', ['84471200']),
    ('CIRCULAR KNITTING MACHINE, model B16 20, 230011002000MM', ['84471100', '84471200']),
])
def test_machine_mechanism_and_stated_drive_precede_suffix(description, codes):
    assert [o['code'] for o in textile_scenarios(description, CATALOG)] == codes


@pytest.mark.parametrize('description', ['SPARE PARTS FOR CROCHET MACHINE', 'MOTOR FOR CROCHET MACHINE', 'CONTROL PANEL FOR CROCHET MACHINE', 'Crochet hook', 'Kim cho máy dệt móc', 'PCB for inverter', 'SEWING MACHINE with subsidiary embroidery function', 'Máy khâu thông thường có chức năng thêu phụ'])
def test_machine_parts_and_hand_tools_do_not_inherit_the_whole_machine_branch(description):
    assert product_function(description) is None


def test_crochet_does_not_get_circular_non_electric_or_sewing_options_from_heading_title():
    eligible, excluded = function_candidates(DESCRIPTION, CATALOG)
    assert {c['code'] for c in eligible} == {'84479010'}
    assert {'84471100', '84472010', '84472020', '84479020', '84522900'} <= {c['code'] for c in excluded}


def test_completion_replaces_wrong_summary_and_citations_and_preserves_actual_input():
    options = textile_scenarios(DESCRIPTION, CATALOG)
    answer = complete_textile_analysis({'legal_analysis': {'summary': 'Crochet luôn là dệt kim phẳng', 'hypotheses': [{'code': '84472010'}]}}, DESCRIPTION, options, SOURCES)
    assert answer['status'] == 'COMPLETED' and answer['recommended_code'] == '84479010'
    assert not answer['legal_analysis']['hypotheses']
    assert answer['legal_analysis']['product_facts'] == [DESCRIPTION]
    assert '84479010' in answer['legal_analysis']['summary']
    unknown = 'CROCHET MACHINE'
    unknown_options = textile_scenarios(unknown, CATALOG)
    conditional = complete_textile_analysis({}, unknown, unknown_options, SOURCES)
    first = conditional['legal_analysis']['hypotheses'][0]
    assert 'crochet' in answer['source_chunk_ids']
    assert matching_textile_hypothesis(first, unknown_options, SOURCES)
    assert not matching_textile_hypothesis({**first, 'source_chunk_ids': ['heading', 'r1', 'r6']}, unknown_options, SOURCES)
    assert not matching_textile_hypothesis({**first, 'code': '84472010', 'assumptions': ['Crochet là dệt kim phẳng']}, unknown_options, SOURCES)


def test_heading_title_alone_cannot_support_or_promote_secondary_interpretation():
    options = textile_scenarios(DESCRIPTION, CATALOG)
    assert complete_textile_analysis({}, DESCRIPTION, options, SOURCES[:3]) == {}
    assert complete_textile_analysis({}, DESCRIPTION, options, [c for c in SOURCES if c['chunk_id'] != 'crochet']) == {}


def test_pdf_line_wrapping_does_not_hide_the_competing_mechanism():
    wrapped_sources = [{**c, 'content': c['content'].replace('Máy dệt kim phẳng bao gồm', 'Máy dệt\nkim phẳng bao gồm').replace('máy dệt móc', 'máy dệt\nmóc')} for c in SOURCES]
    result = complete_textile_analysis({}, DESCRIPTION, textile_scenarios(DESCRIPTION, CATALOG), wrapped_sources)
    assert result['recommended_code'] == '84479010'
    assert not result['legal_analysis']['hypotheses']
    assert contains_phrase('Máy dệt\nkim phẳng bao gồm', 'Máy dệt kim phẳng bao gồm')
    assert not contains_phrase('Máy dệt kim phẳng; Nhóm này bao gồm các loại khác', 'Máy dệt kim phẳng bao gồm')
    assert phrase_search_pattern('Máy dệt kim phẳng bao gồm') == 'Máy[[:space:]]+dệt[[:space:]]+kim[[:space:]]+phẳng[[:space:]]+bao[[:space:]]+gồm'


def retrieved():
    return [{'id': c['chunk_id'], 'document_id': 'doc', 'title': 'Chú giải', 'page': 1, 'content': c['content'],
             'semantic_score': .9, 'keyword_score': .5, 'rerank_score': .9} for c in SOURCES]


def test_entire_flow_repairs_single_wrong_model_proposal_even_if_it_has_real_source_ids(monkeypatch):
    class Provider(AIProvider):
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            context = json.loads(messages[1]['content'])
            assert {c['code'] for c in context['candidates']} == {'84479010'}
            if 'interpret the FULL meaning' in messages[0]['content']:
                return json.dumps({'product_name': 'Máy dệt móc', 'meaning': 'Máy dệt móc', 'scope': 'whole', 'identity_eligible_codes': ['84479010'], 'facts': [], 'missing_attributes': []})
            return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                {'code': '84472010', 'assumptions': ['Crochet là dệt kim phẳng'], 'reasoning': 'Nhóm 8447', 'source_chunk_ids': ['heading', 'r1']}]}})
    async def retrieve(*_): return retrieved()
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify(DESCRIPTION, CATALOG, Provider()))
    assert result['status'] == 'COMPLETED'
    assert result['recommended_code'] == '84479010'
    assert not result['legal_analysis']['hypotheses']
    assert result['legal_analysis']['product_understanding']['product_name'] == 'Máy dệt móc'


def test_final_gate_rejects_wrong_assumption_even_when_provider_bypasses_repairs(monkeypatch):
    class Provider:
        async def classifyProduct(self, *_):
            return {'status': 'COMPLETED', 'recommended_code': '84472010', 'legal_analysis': {
                'legal_steps': [{'rule': 'Quy tắc 1', 'application': 'Nhóm 8447', 'source_chunk_ids': ['r1']}],
                'hypotheses': [{'code': '84472010', 'assumptions': ['Crochet là dệt kim phẳng'], 'reasoning': 'Máy dệt', 'source_chunk_ids': ['flat', 'heading', 'r1', 'r6']}]}}
    async def retrieve(*_): return retrieved()
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify(DESCRIPTION, CATALOG, Provider()))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert not result['legal_analysis']['hypotheses']
    assert not result['normalized_product'].get('provisional_code')


def test_missing_correct_catalog_branch_requests_recovery(monkeypatch):
    class Provider:
        async def classifyProduct(self, *_): return {'status': 'INSUFFICIENT_EVIDENCE'}
    async def retrieve(*_): return retrieved()
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify('CROCHET MACHINE making braid, 1.5 kW', CATALOG[2:4], Provider()))
    assert result['catalog_hints']['queries'] == ['máy dệt kim', 'máy khâu đính', 'máy tạo búi']
    assert not result['normalized_product'].get('provisional_code')


def test_missing_primary_crochet_branch_cannot_promote_flat_interpretation(monkeypatch):
    options = textile_scenarios(DESCRIPTION, CATALOG[2:4])
    assert not options
    assert complete_textile_analysis({}, DESCRIPTION, options, SOURCES) == {}
    class Provider:
        async def classifyProduct(self, *_): return {'status': 'INSUFFICIENT_EVIDENCE'}
    async def retrieve(*_): return retrieved()
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify(DESCRIPTION, CATALOG[2:4], Provider()))
    assert result['catalog_hints']['queries'] == ['máy dệt kim', 'máy khâu đính', 'máy tạo búi']
    assert not result['normalized_product'].get('provisional_code')


def test_final_gate_does_not_publish_secondary_code_while_primary_catalog_is_missing(monkeypatch):
    secondary = complete_textile_analysis({}, 'FLAT KNITTING MACHINE, 1.5 kW', textile_scenarios('FLAT KNITTING MACHINE, 1.5 kW', CATALOG), SOURCES)
    class Provider:
        async def classifyProduct(self, *_): return secondary
    async def retrieve(*_): return retrieved()
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    result = asyncio.run(rag.classify(DESCRIPTION, CATALOG[2:4], Provider()))
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert not result['legal_analysis']['hypotheses']
    assert result['catalog_hints']['queries']
