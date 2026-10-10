import asyncio
import json
from app.ai_client import AIProvider
from app.product_understanding import validated_understanding, identity_review_errors


def test_defined_identity_and_known_drive_cannot_become_missing_attributes():
    sources = [{'chunk_id': 'other-machine', 'content': 'Máy dệt kim phẳng sợi dọc (máy Raschel).'},
               {'chunk_id': 'definition', 'content': 'Máy sản xuất đồ trang trí (máy dệt viền, máy dệt móc).'}]
    result = validated_understanding({'product_name': 'Máy dệt kim phẳng', 'meaning': 'Giả định loại máy khác',
        'missing_attributes': ['identity', 'mechanism', 'drive', 'material'], 'identity_eligible_codes': ['84472010']},
        'COMPUTERIZED CROCHET MACHINE\nPOWER: 1.5KW', [{'code': '84479010'}], sources)
    assert result['product_name'] == 'Máy dệt móc'
    assert result['identity_eligible_codes'] == ['84479010']
    assert not result['missing_attributes']
    assert result['definition_source_ids'] == ['definition']


def test_missing_drive_varies_drive_only_and_cannot_vary_machine_identity():
    result = validated_understanding({'missing_attributes': ['identity', 'mechanism', 'drive']}, 'CROCHET MACHINE', [], [])
    assert result['missing_attributes'] == ['drive']
    assert identity_review_errors({'legal_analysis': {'hypotheses': [{'code': '84479010', 'assumed_attributes': [{'attribute': 'identity', 'value': 'Flat knitting machine'}]}]}}, {**result, 'identity_eligible_codes': ['84479010']})


def test_unquoted_facts_and_false_definition_citations_are_rejected():
    result = validated_understanding({'facts': [
        {'attribute': 'material', 'value': 'thép', 'product_quote': 'steel'},
        {'attribute': 'identity', 'value': 'Máy dệt kim phẳng', 'basis': 'definition', 'product_quote': 'MACHINE', 'source_quote': 'Máy dệt kim phẳng', 'source_chunk_ids': ['wrong']},
    ]}, 'MACHINE MODEL: X', [], [{'chunk_id': 'wrong', 'content': 'QUI TẮC 6'}])
    assert not result['facts']


def test_model_digits_are_not_power_and_declared_power_cannot_be_changed():
    result = validated_understanding({'facts': [
        {'attribute': 'power', 'value': '45 kW', 'product_quote': 'TVF225M-8-45-152'},
        {'attribute': 'power', 'value': '15 kW', 'product_quote': '1.5 kW'},
        {'attribute': 'phase', 'value': 'ba pha', 'product_quote': '4T'},
        {'attribute': 'diameter', 'value': '350 mm', 'product_quote': 'φ350'},
    ]}, 'MODEL TVF225M-8-45-152 4T; POWER 1.5 kW; φ350', [], [])
    assert not result['facts']
    correct = validated_understanding({'facts': [{'attribute': 'power', 'value': '1500 W', 'product_quote': '1.5 kW'}]}, 'POWER 1.5 kW', [], [])
    assert correct['facts'][0]['value'] == '1500 W'


def test_known_material_cannot_be_assumed_again_and_assumptions_need_attribute_tags():
    understanding = {'known_attributes': ['identity', 'material'], 'missing_attributes': ['packaging'], 'identity_eligible_codes': ['61091010']}
    wrong = {'code': '61091010', 'assumptions': ['Giả định polyester'], 'assumed_attributes': [{'attribute': 'material', 'value': 'polyester'}]}
    assert identity_review_errors({'legal_analysis': {'hypotheses': [wrong]}}, understanding)
    wrong.pop('assumed_attributes')
    assert identity_review_errors({'legal_analysis': {'hypotheses': [wrong]}}, understanding)
    good = {'code': '61091010', 'assumptions': ['Đóng gói để bán lẻ'], 'assumed_attributes': [{'attribute': 'packaging', 'value': 'đóng gói để bán lẻ'}]}
    assert not identity_review_errors({'legal_analysis': {'hypotheses': [good]}}, understanding)


def test_power_range_alias_keeps_valid_servo_scenarios_but_cannot_change_known_power():
    understanding = {'known_attributes': ['identity'], 'missing_attributes': ['power', 'phase'],
                     'identity_eligible_codes': ['85015229']}
    hypothesis = {'code': '85015229', 'assumptions': ['Công suất trên 1 đến 37,5 kW, đa pha'],
                  'assumed_attributes': [{'attribute': 'power_range', 'value': 'trên 1 đến 37,5 kW'},
                                         {'attribute': 'number_of_phases', 'value': 'đa pha'}]}
    assert not identity_review_errors({'legal_analysis': {'hypotheses': [hypothesis]}}, understanding)
    assert identity_review_errors({'legal_analysis': {'hypotheses': [hypothesis]}},
        {**understanding, 'known_attributes': ['identity', 'power'], 'missing_attributes': ['phase']})


def test_attribute_aliases_are_shared_by_declared_and_missing_facts():
    result = validated_understanding({'facts': [{'attribute': 'rated_power', 'value': '45 kW', 'product_quote': '45 kW'}],
        'missing_attributes': ['power_range', 'phase_count']}, 'SYNCHRONOUS MOTOR, 45 kW', [], [])
    assert result['facts'][0]['attribute'] == 'power'
    assert result['missing_attributes'] == ['phase']


def test_formatted_candidate_code_is_not_mistaken_for_a_different_article():
    understanding = {'known_attributes': ['identity'], 'missing_attributes': ['power'], 'identity_eligible_codes': ['85015229']}
    hypothesis = {'code': '8501.52.29', 'assumptions': ['Công suất trên 1 kW đến 37,5 kW'],
                  'assumed_attributes': [{'attribute': 'power_range', 'value': 'trên 1 kW đến 37,5 kW'}]}
    assert not identity_review_errors({'legal_analysis': {'hypotheses': [hypothesis]}}, understanding)
    assert identity_review_errors({'legal_analysis': {'hypotheses': [{**hypothesis, 'code': '8504.40.90'}]}}, understanding)


def test_understanding_call_has_no_assumptions_and_returns_only_verified_contract():
    class Provider(AIProvider):
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            assert 'DO NOT make any product assumption' in messages[0]['content']
            context = json.loads(messages[1]['content'])
            assert context['product_description'] == 'CROCHET MACHINE, 1.5 kW'
            return json.dumps({'product_name': 'Máy dệt móc', 'meaning': 'Máy dệt móc', 'identity_eligible_codes': ['84479010'], 'missing_attributes': ['material', 'drive']})
    result = asyncio.run(Provider().understandProduct('CROCHET MACHINE, 1.5 kW', [{'code': '84479010'}], [{'chunk_id': 'd', 'content': 'máy dệt móc'}]))
    assert result['product_name'] == 'Máy dệt móc'
    assert not result['missing_attributes']


def test_known_recipe_percentages_do_not_hide_the_unknown_remainder():
    description = 'Cơm chiên: gạo: 55%; tôm: 11%; thịt lợn: 10%; cà rốt: 5%; hành tây: 5%; gia vị: 4%.'
    result = validated_understanding({'facts': [{'attribute': 'composition', 'value': 'Gạo 55%', 'product_quote': 'gạo: 55%'}],
        'missing_attributes': ['composition'], 'identity_eligible_codes': ['16052990']}, description, [{'code': '16052990'}, {'code': '16024990'}], [])
    assert 'composition.declared' in result['known_attributes']
    assert result['missing_attributes'] == ['composition.balance']
    assert result['identity_eligible_codes'] == ['16052990', '16024990']
    hypothesis = {'code': '16052990', 'assumptions': ['10% còn lại là rau'], 'assumed_attributes': [{'attribute': 'composition.balance', 'value': '10% rau'}]}
    assert not identity_review_errors({'legal_analysis': {'hypotheses': [hypothesis]}}, result)


def test_set_attributes_are_scoped_to_the_correct_article():
    result = validated_understanding({'scope': 'set',
        'facts': [{'attribute': 'tie.material', 'value': 'Cà vạt cotton', 'product_quote': 'cà vạt cotton'}],
        'missing_attributes': ['tie.material', 'socks.material']}, 'Bộ quà gồm cà vạt cotton và vớ', [{'code': '61159600'}], [])
    assert 'socks.material' in result['missing_attributes'] and 'tie.material' not in result['missing_attributes']
    hypothesis = {'code': '61159600', 'assumptions': ['Vớ bằng sợi tổng hợp'], 'assumed_attributes': [{'attribute': 'socks.material', 'value': 'sợi tổng hợp'}]}
    assert not identity_review_errors({'legal_analysis': {'hypotheses': [hypothesis]}}, result)


def test_unknown_material_is_not_a_confirmed_fact_and_gift_does_not_prove_retail_packaging():
    result = validated_understanding({'facts': [
        {'attribute': 'caravat.material', 'value': 'chưa xác định chất liệu caravat', 'product_quote': 'caravat'},
        {'attribute': 'socks.material', 'value': 'polyester', 'product_quote': 'vớ'},
    ], 'missing_attributes': []}, 'Bộ quà tặng gồm caravat và vớ', [{'code': '62152090'}], [])
    assert not result['facts']
    assert {'tie.material', 'socks.material', 'packaging.retail', 'shared_activity', 'essential_character'} <= set(result['missing_attributes'])
    assert 'được đóng gói chung' not in result['meaning']


def test_missing_valve_attributes_are_derived_from_actual_catalog_conditions():
    from test_catalog_conditions import CATALOG
    result = validated_understanding({'missing_attributes': [], 'identity_eligible_codes': ['84812090']}, 'PNEUMATIC VALVE φ350', CATALOG, [])
    assert {'construction', 'drive', 'material', 'diameter', 'use'} <= set(result['missing_attributes'])
    assert {'84812011', '84812019', '84812090'} <= set(result['identity_eligible_codes'])
