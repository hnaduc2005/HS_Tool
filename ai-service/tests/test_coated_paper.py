import asyncio
import json
import pytest
from app.coated_paper import paper_profile, paper_candidates, paper_missing, complete_paper_analysis
from app.product_understanding import validated_understanding, identity_review_errors
from app.ai_client import AIProvider
from app import rag

DESCRIPTION = 'Giấy trang trí phủ PU, QC: 1270MM *30G~45G, dùng dán giả vân gỗ trên bề mặt ván, không nhãn hiệu, có nhãn hàng hóa, hàng mới 100%'
CATALOG = [
    {'code': '48115949', 'description': 'Giấy và bìa phủ bằng plastic: → Dạng cuộn có chiều rộng không quá 15 cm hoặc tờ không có chiều nào trên 36 cm: → Loại khác'},
    {'code': '48115999', 'description': 'Giấy và bìa phủ bằng plastic: → Loại khác: → Loại khác'},
    {'code': '48115199', 'description': 'Giấy phủ plastic đã tẩy trắng, định lượng trên 150 g/m2: → Loại khác: → Loại khác'},
    {'code': '48119049', 'description': 'Giấy khác: → Dạng cuộn có chiều rộng không quá 15 cm hoặc tờ không có chiều nào trên 36 cm: → Loại khác'},
    {'code': '48119099', 'description': 'Giấy, bìa, tấm xenlulo và màng xơ sợi xenlulo khác: → Loại khác: → Loại khác'},
    {'code': '48119092', 'description': 'Giấy khác: → Loại khác: → Giấy tạo vân (SEN)'},
    {'code': '48119091', 'description': 'Giấy khác: → Loại khác: → Tấm phủ sàn'},
    {'code': '48114190', 'description': 'Giấy và bìa dính: → Loại tự dính: → Loại khác'},
    {'code': '48142099', 'description': 'Giấy dán tường phủ plastic: → Loại khác'},
    {'code': '39219090', 'description': 'Tấm plastic khác'},
]
SOURCES = [
    {'chunk_id': 'heading', 'content': '48.11 - Giấy đã tráng, phủ, trang trí hoặc in bề mặt. 4811.51 - Đã tẩy trắng, định lượng trên 150g/m2. 4811.59 - Loại khác, phủ plastic. 4811.90 - Giấy khác.'},
    {'chunk_id': 'decoration', 'content': '(D) Giấy đã in mẫu hình và tạo vân bề mặt; hoa văn thứ yếu so với công dụng của giấy.'},
    {'chunk_id': 'thickness', 'content': 'Độ dày lớp plastic không vượt quá một nửa tổng độ dày.'},
    {'chunk_id': 'rule1', 'content': 'QUY TẮC 1: Phân loại theo nội dung nhóm và chú giải.'},
    {'chunk_id': 'rule6', 'content': 'QUY TẮC 6: So sánh các phân nhóm cùng cấp.'},
]


@pytest.mark.parametrize('description', [DESCRIPTION, 'NK144#&' + DESCRIPTION, DESCRIPTION.upper(), DESCRIPTION.replace('1270MM', '127 cm'), DESCRIPTION.replace(', ', '\n')])
def test_full_decorative_paper_meaning_selects_other_paper_without_assumptions(description):
    raw = {'product_name': 'Giấy phủ plastic', 'missing_attributes': ['bleaching_status', 'packaging.form', 'material.base_paper'],
        'identity_eligible_codes': ['48115999']}
    understanding = validated_understanding(raw, description, CATALOG, SOURCES)
    assert '48119099' in understanding['identity_eligible_codes']
    assert '48115999' not in understanding['identity_eligible_codes']
    assert not understanding['missing_attributes']
    assert 'ván' in understanding['meaning'] and 'PU' in understanding['product_name']
    assert any(fact['attribute'] == 'use' and 'bề mặt ván' in fact['value'].casefold() for fact in understanding['facts'])
    result = complete_paper_analysis({'status': 'INSUFFICIENT_EVIDENCE'}, description, CATALOG, SOURCES, understanding)
    assert result['status'] == 'COMPLETED' and result['recommended_code'] == '48119099'
    assert not result['missing_information'] and not result['legal_analysis']['hypotheses']
    assert not result['legal_analysis']['limitations']
    assert len(result['source_chunk_ids']) == 4
    assert 'g/m²' not in next(fact['value'] for fact in understanding['facts'] if fact['attribute'] == 'grammage.declared')
    assert rag.normalize(description)['material'] == 'giấy'


def test_sufficient_small_roll_uses_its_actual_size_child():
    description = DESCRIPTION.replace('1270MM', '130MM') + ', dạng cuộn'
    result = complete_paper_analysis({}, description, CATALOG, SOURCES, None)
    assert result['recommended_code'] == '48119049'
    assert 'không quá ngưỡng cuộn 15 cm' in result['legal_analysis']['legal_steps'][-1]['application']


def test_a_missing_discriminator_is_preserved_instead_of_forcing_completed():
    description = DESCRIPTION.replace('1270MM', '300MM')
    profile = paper_profile(description)
    assert paper_missing(profile) == ['dimensions.length']
    sentinel = {'status': 'CONDITIONAL'}
    assert complete_paper_analysis(sentinel, description, CATALOG, SOURCES, None) is sentinel


def test_declared_plastic_film_is_distinct_from_pu_surface_finish():
    description = DESCRIPTION + ', được phủ màng PU'
    profile = paper_profile(description)
    assert profile['plastic_layer'] and not profile['decorative_finish']
    assert '48119099' not in {row['code'] for row in paper_candidates(profile, CATALOG)}
    result = complete_paper_analysis({}, description, CATALOG, SOURCES, None)
    assert {h['code'] for h in result['legal_analysis']['hypotheses']} == {'48115999'}


def test_fully_declared_plastic_film_needs_no_hypothetical_product_details():
    description = 'Giấy phủ màng PU, khổ 1270MM, định lượng 40g/m2, không tẩy trắng, dạng cuộn, không tự dính, lớp plastic chiếm 30% tổng độ dày'
    profile = paper_profile(description)
    assert profile['plastic_layer'] and profile['thickness_ratio'] == 30
    assert not paper_missing(profile)
    result = complete_paper_analysis({}, description, CATALOG, SOURCES, None)
    assert result['status'] == 'COMPLETED' and result['recommended_code'] == '48115999'
    assert not result['missing_information'] and not result['legal_analysis']['hypotheses']
    assert not any('giả định' in question['answer'].casefold() for question in result['legal_analysis']['decision_questions'])


@pytest.mark.parametrize('suffix', [', tự dính', ', dùng dán tường', ', dùng phủ sàn', ', cắt thành hình tròn', ', lớp PU chiếm 70% tổng độ dày'])
def test_explicit_changes_do_not_inherit_the_decorative_paper_completed_code(suffix):
    result = complete_paper_analysis({}, DESCRIPTION + suffix, CATALOG, SOURCES, None)
    assert result.get('recommended_code') != '48119099'


@pytest.mark.parametrize('suffix', [', dùng dán tường', ', dùng phủ sàn', ', cắt thành hình tròn', ', lớp PU chiếm 70% tổng độ dày'])
def test_other_declared_product_families_do_not_receive_decorative_paper_missing_fields(suffix):
    understanding = validated_understanding({'missing_attributes': ['purpose.detail']}, DESCRIPTION + suffix, CATALOG, SOURCES)
    assert understanding['missing_attributes'] == ['purpose.detail']
    assert 'coating.form' not in understanding['missing_attributes']


def test_negations_do_not_change_surface_finish_to_film_adhesive_or_wallpaper():
    description = DESCRIPTION + ', không phủ màng plastic, không tự dính, không tráng keo, không dùng dán tường'
    result = complete_paper_analysis({}, description, CATALOG, SOURCES, None)
    assert result['recommended_code'] == '48119099'


@pytest.mark.parametrize('source_to_omit', ['heading', 'decoration', 'rule1', 'rule6'])
def test_no_classification_is_fabricated_when_its_legal_source_is_missing(source_to_omit):
    result = complete_paper_analysis({}, DESCRIPTION, CATALOG, [source for source in SOURCES if source['chunk_id'] != source_to_omit], None)
    assert not result.get('recommended_code')


def test_no_similar_but_absent_eight_digit_code_is_substituted():
    result = complete_paper_analysis({}, DESCRIPTION, [c for c in CATALOG if c['code'] != '48119099'], SOURCES, None)
    assert not result.get('recommended_code')


def test_whole_product_must_be_paper_instead_of_a_machine_or_board_containing_paper():
    assert not paper_profile('Máy phủ PU lên giấy trang trí, dùng trên bề mặt ván')
    assert not paper_profile('Ván phủ giấy trang trí PU')


def test_entire_flow_recovers_a_wrong_model_answer_without_waiting_for_irrelevant_facts(monkeypatch):
    async def retrieve(*args):
        return [{'id': source['chunk_id'], 'content': source['content'], 'document_id': 'doc', 'title': 'Chú giải',
                 'page': 1, 'semantic_score': .8, 'keyword_score': .8, 'rerank_score': .8} for source in SOURCES]
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    class Provider(AIProvider):
        calls = 0
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            if 'product_understanding' not in context:
                return json.dumps({'product_name': 'Giấy phủ plastic', 'identity_eligible_codes': ['48115999'],
                    'missing_attributes': ['packaging.form', 'bleaching_status']})
            codes = {candidate['code'] for candidate in context['candidates']}
            assert '48119099' in codes and '48115999' not in codes
            return json.dumps({'status': 'CONDITIONAL', 'recommended_code': '48115990',
                'legal_analysis': {'hypotheses': [{'code': '48115999', 'assumptions': []}]}})
    provider = Provider()
    result = asyncio.run(rag.classify(DESCRIPTION, CATALOG, provider))
    assert result['status'] == 'COMPLETED' and result['recommended_code'] == '48119099'
    assert provider.calls == 2
    assert not result['legal_analysis']['hypotheses'] and not result['missing_information']
    assert result['sources'] and not identity_review_errors(result, result['legal_analysis']['product_understanding'])
    assert {item['code'] for item in result['legal_analysis']['alternatives']} == {'48115999', '48119049'}
    assert '48115999' not in result['legal_analysis']['product_understanding']['identity_eligible_codes']
