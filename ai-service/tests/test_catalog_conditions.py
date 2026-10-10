import asyncio
import json
from app.ai_client import AIProvider
from app.catalog_conditions import catalog_branch, residual_options, valve_scenarios, matching_valve_hypothesis, complete_valve_analysis

CATALOG = [
    {'code': '84812011', 'description': 'Van dùng trong truyền động dầu thủy lực hoặc khí nén: → Van cổng điều khiển bằng tay có đường kính trong cửa nạp hoặc cửa thoát trên 5 cm nhưng không quá 40 cm: → Bằng sắt hoặc thép'},
    {'code': '84812019', 'description': 'Van dùng trong truyền động dầu thủy lực hoặc khí nén: → Van cổng điều khiển bằng tay có đường kính trong cửa nạp hoặc cửa thoát trên 5 cm nhưng không quá 40 cm: → Loại khác'},
    {'code': '84812020', 'description': 'Van dùng trong truyền động dầu thủy lực hoặc khí nén: → Bằng đồng hoặc hợp kim đồng, có đường kính trong không quá 2,5 cm, hoặc bằng plastic có đường kính trong từ 1 cm đến 2,5 cm'},
    {'code': '84812090', 'description': 'Van dùng trong truyền động dầu thủy lực hoặc khí nén: → Loại khác'},
]
SOURCES = [{'chunk_id': 'valves', 'content': '84.81. - Vòi, van. 8481.20 - Van dùng trong truyền động khí nén.'},
           {'chunk_id': 'motors', 'content': '84.12 - Động cơ và mô tơ khí nén.'}]


def test_nested_other_is_distinct_from_parent_other():
    assert catalog_branch(CATALOG[1]) != catalog_branch(CATALOG[3])
    options = valve_scenarios('PNEUMATIC VALVE φ350', CATALOG)
    assert [o['code'] for o in options] == ['84812090', '84812011', '84812019']
    # Codes are derived from catalog terms, not hardcoded to this sample's answer.
    changed = [{**c, 'code': '123456' + c['code'][-2:]} for c in CATALOG]
    assert valve_scenarios('PNEUMATIC VALVE φ350', changed)[0]['code'] == '12345690'


def test_unknown_material_policy_only_proposes_existing_other_90():
    assert residual_options('PNEUMATIC VALVE φ350', CATALOG)[0]['code'] == '84812090'
    assert not residual_options('steel pneumatic valve', CATALOG)
    assert not residual_options('pneumatic valve', CATALOG[:3])


def test_known_manual_gate_material_and_size_are_not_forced_to_90():
    assert [o['code'] for o in valve_scenarios('Manual steel gate valve DN350 for pneumatic fluid power', CATALOG)] == ['84812011']
    assert [o['code'] for o in valve_scenarios('Manual brass gate valve DN350 for pneumatic fluid power', CATALOG)] == ['84812019']
    assert [o['code'] for o in valve_scenarios('Manual steel gate valve DN450 for pneumatic fluid power', CATALOG)] == ['84812090']
    assert [o['code'] for o in valve_scenarios('Butterfly valve with pneumatic actuator φ350', CATALOG)] == ['84812090']
    assert [o['code'] for o in valve_scenarios('Brass pneumatic valve DN15', CATALOG)] == ['84812020']
    outside = valve_scenarios('Manual steel gate valve DN450 for pneumatic fluid power', CATALOG)
    assert not any('tự động' in a for a in outside[0]['assumptions'])


def test_valve_assumptions_preserve_working_medium_and_actuation():
    assert not valve_scenarios('Water butterfly valve with pneumatic actuator φ350', CATALOG)
    hydraulic = valve_scenarios('Hydraulic valve φ350', CATALOG)
    assert all('dầu thủy lực' in option['assumptions'][0] for option in hydraulic)
    assert [o['code'] for o in valve_scenarios('Pneumatic gate valve, not manual, φ350', CATALOG)] == ['84812090']


def test_rejects_size_only_reasoning_and_wrong_heading_citation():
    options = valve_scenarios('PNEUMATIC VALVE φ350', CATALOG)
    bad = {'code': '84812019', 'assumptions': ['Đường kính 350 mm phù hợp'], 'reasoning': 'Quy tắc 1 và 6', 'source_chunk_ids': ['valves']}
    assert not matching_valve_hypothesis(bad, options, SOURCES)
    option = options[2]
    good = {**bad, 'assumptions': option['assumptions']}
    assert matching_valve_hypothesis(good, options, SOURCES)
    assert not matching_valve_hypothesis({**good, 'source_chunk_ids': ['motors']}, options, SOURCES)


def test_repairs_one_wrong_hypothesis_and_prioritizes_valid_parent_other():
    class Provider(AIProvider):
        calls = 0
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            if self.calls == 1:
                return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                    {'code': '84812019', 'assumptions': ['Đường kính phù hợp'], 'reasoning': 'Quy tắc 6', 'source_chunk_ids': ['motors']} ]}})
            assert 'EVERY required_valve_scenarios' in messages[-1]['content']
            return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                {'code': o['code'], 'assumptions': o['assumptions'], 'reasoning': 'Xét đủ điều kiện', 'source_chunk_ids': ['valves']}
                for o in reversed(context['required_valve_scenarios'])]}})
    provider = Provider()
    result = asyncio.run(provider.classifyProduct('PNEUMATIC VALVE φ350', CATALOG, SOURCES))
    assert provider.calls == 2
    assert result['legal_analysis']['hypotheses'][0]['code'] == '84812090'


def test_supported_valve_cases_are_completed_without_model_omissions():
    sources = SOURCES + [{'chunk_id': 'r1', 'content': 'QUI TẮC 1'}, {'chunk_id': 'r6', 'content': 'RULE 6'}]
    options = valve_scenarios('PNEUMATIC VALVE φ350', CATALOG)
    result = complete_valve_analysis({'status': 'COMPLETED', 'recommended_code': '84812019'}, 'PNEUMATIC VALVE φ350', options, sources)
    assert result['status'] == 'CONDITIONAL'
    assert [h['code'] for h in result['legal_analysis']['hypotheses']] == ['84812090', '84812011', '84812019']
    assert all({'valves', 'r1', 'r6'} <= set(h['source_chunk_ids']) for h in result['legal_analysis']['hypotheses'])
    assert all(matching_valve_hypothesis(h, options, sources) for h in result['legal_analysis']['hypotheses'])
    assert result['legal_analysis']['product_facts'] == ['PNEUMATIC VALVE φ350']
    incomplete_sources = complete_valve_analysis({}, 'PNEUMATIC VALVE φ350', options, SOURCES)
    assert incomplete_sources == {}, 'Do not construct legal steps when rule sources are absent'
