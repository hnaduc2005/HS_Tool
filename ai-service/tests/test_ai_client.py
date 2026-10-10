import asyncio
import math
import json
import httpx
from app.ai_client import AIProvider, GeminiProvider

class FakeProvider(AIProvider):
    async def chat(self, messages):
        assert 'Never invent a code' in messages[0]['content']
        assert 'legal_analysis.hypotheses' in messages[0]['content']
        assert '61091010' in messages[1]['content']
        return '{"status":"COMPLETED","recommended_code":"61091010","source_chunk_ids":["chunk-1"]}'
    async def embed(self, texts, task_type='SEMANTIC_SIMILARITY'): return [[0.1, 0.2] for _ in texts]

def test_ai_provider_contract():
    provider = FakeProvider()
    result = asyncio.run(provider.classifyProduct('Áo thun nam cotton', [{'code': '61091010'}], [{'chunk_id': 'chunk-1'}]))
    assert result['recommended_code'] == '61091010'
    assert asyncio.run(provider.embed(['a', 'b'])) == [[0.1, 0.2], [0.1, 0.2]]


def test_missing_material_answer_is_retried_for_explicit_conditional_proposals():
    class ConditionalProvider(FakeProvider):
        calls = 0
        async def chat(self, messages):
            self.calls += 1
            assert 'decision_questions' in messages[0]['content']
            assert 'classification_mode="separate"' in messages[0]['content']
            if self.calls == 1:
                return '{"status":"INSUFFICIENT_EVIDENCE","missing_information":["Chưa khai chất liệu"],"legal_analysis":{"hypotheses":[]}}'
            assert 'Missing product facts alone' in messages[-1]['content']
            return '{"status":"CONDITIONAL","legal_analysis":{"hypotheses":[{"code":"62152090"}]}}'
    ai = ConditionalProvider()
    result = asyncio.run(ai.classifyProduct('Bộ quà tặng gồm caravat và vớ', [{'code': '62152090'}], [{'chunk_id': 'rule-3'}]))
    assert ai.calls == 2
    assert result['status'] == 'CONDITIONAL'


def test_gift_socks_do_not_inherit_a_garment_note_outside_its_scope():
    class ScopeProvider(FakeProvider):
        calls = 0
        async def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                assert 'scope_checks' in messages[1]['content']
                return '{"status":"CONDITIONAL","legal_analysis":{"hypotheses":[{"code":"62152090","classification_mode":"separate","reasoning":"Theo Chú giải 14, phân loại riêng tất cả hàng dệt may.","assumptions":[],"items":[{"code":"62152090"},{"code":"61159500"}]}]}}'
            assert 'Correct the scope error' in messages[-1]['content']
            return '{"status":"CONDITIONAL","legal_analysis":{"hypotheses":[{"code":"62152090","classification_mode":"single","reasoning":"Giả định bộ bán lẻ đồng bộ, không có món chi phối, xét Quy tắc 3(c)."}]}}'
    ai = ScopeProvider()
    result = asyncio.run(ai.classifyProduct('Bộ quà tặng gồm caravat và vớ', [{'code': '62152090'}, {'code': '61159500'}], [
        {'chunk_id': 'scope-61', 'content': 'Chú giải 14 Phần XI: khái niệm hàng dệt may sẵn nghĩa là các hàng hóa của các nhóm từ 61.01 đến 61.14.'},
    ]))
    assert ai.calls == 2
    assert result['legal_analysis']['hypotheses'][0]['classification_mode'] == 'single'

def test_gift_repairs_missing_material_and_equal_character_scenarios():
    class MaterialProvider(FakeProvider):
        calls = 0
        async def chat(self, messages):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            assert len(context['required_scenarios']) == 4
            if self.calls == 1:
                return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                    {'code': '62151090', 'classification_mode': 'single', 'reasoning': 'Cà vạt lụa chi phối: 3(b).'},
                ]}})
            assert 'Cover every required_scenarios' in messages[-1]['content']
            return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                {'code': '62152090', 'classification_mode': 'single', 'reasoning': 'Hai món không chi phối; 3(c).'},
                {'code': '62151090', 'classification_mode': 'single', 'reasoning': 'Hai món không chi phối; 3(c).'},
                {'code': '61159500', 'classification_mode': 'single', 'reasoning': 'Vớ cotton chi phối; 3(b).'},
                {'code': '62152090', 'classification_mode': 'separate', 'items': [{'code': '62152090'}, {'code': '61159600'}]},
            ]}})
    ai = MaterialProvider()
    result = asyncio.run(ai.classifyProduct('Bộ quà tặng gồm caravat và vớ',
        [{'code': code, 'description': 'Loại thông thường'} for code in ('62152090', '62151090', '61159500', '61159600')],
        [{'chunk_id': 'rule-3', 'content': 'Rule 3(c): last in numerical order'}]))
    assert ai.calls == 2
    assert len(result['legal_analysis']['hypotheses']) == 4


def test_gift_scenario_plan_keeps_stated_materials_and_requires_real_branches():
    from app.ai_client import gift_scenario_plan
    candidates = [{'code': code} for code in ('62152090', '62151090', '61159500', '61159600')]
    chunks = [{'content': 'last in numerical order'}]
    assert not gift_scenario_plan('Bộ cà vạt lụa và vớ cotton', candidates, chunks)
    assert not gift_scenario_plan('Bộ caravat và vớ', candidates[:-1], chunks)
    assert not gift_scenario_plan('Bộ caravat và vớ', candidates, [])

def test_gift_scenario_coverage_requires_a_real_source_for_each_separate_item():
    from app.ai_client import gift_scenario_plan, missing_gift_scenarios
    candidates = [{'code': code} for code in ('62152090', '62151090', '61159500', '61159600')]
    chunks = [{'chunk_id': 'rule-3', 'content': 'last in numerical order'}]
    plan = gift_scenario_plan('Bộ caravat và vớ', candidates, chunks)
    hypotheses = [{
        'code': code, 'classification_mode': 'single', 'assumptions': ['Chất liệu thông thường'],
        'reasoning': reason, 'source_chunk_ids': ['rule-3'],
    } for code, reason in [('62152090', '3(c)'), ('62151090', '3(c)'), ('61159500', '3(b)')]]
    separate = {
        'code': '62152090', 'classification_mode': 'separate', 'assumptions': ['Không phải bộ bán lẻ'],
        'reasoning': 'Phân loại riêng từng mặt hàng.', 'source_chunk_ids': ['rule-3'],
        'items': [{'name': 'Cà vạt', 'code': '62152090', 'source_chunk_ids': ['rule-3']},
                  {'name': 'Vớ', 'code': '61159600', 'source_chunk_ids': ['invented-id']}],
    }
    hypotheses.append(separate)
    assert missing_gift_scenarios(plan, hypotheses, chunks)
    separate['items'][1]['source_chunk_ids'] = ['rule-3']
    assert not missing_gift_scenarios(plan, hypotheses, chunks)

def test_catalog_discovery_returns_search_hints_not_unchecked_codes():
    class SearchProvider(FakeProvider):
        async def chat(self, messages):
            assert 'SEARCH HINTS ONLY' in messages[0]['content']
            return '{"queries":["đồ nội thất bằng gỗ khác","đồ nội thất bằng gỗ khác",42],"heading_hints":["94.03","9403.60.90","invalid"]}'
    result = asyncio.run(SearchProvider().suggestCatalogSearch('Kệ TV bằng gỗ ghép, ván MDF và ván ép'))
    assert result == {'queries': ['đồ nội thất bằng gỗ khác'], 'heading_hints': ['9403', '94036090']}


def test_motor_model_without_power_is_retried_for_real_national_power_scenarios():
    class MotorProvider(FakeProvider):
        calls = 0
        async def chat(self, messages):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            assert len(context['required_power_scenarios']) == 3
            assert context['motor_heading_source_ids'] == ['motor-source']
            if self.calls == 1:
                return json.dumps({'status': 'INSUFFICIENT_EVIDENCE', 'missing_information': ['Thiếu công suất'],
                    'legal_analysis': {'hypotheses': []}})
            assert 'Model numbers do not confirm' in messages[-1]['content']
            return json.dumps({'status': 'CONDITIONAL', 'legal_analysis': {'hypotheses': [
                {'code': option['code'], 'classification_mode': 'single', 'assumptions': option['assumptions'],
                 'reasoning': 'Áp dụng Quy tắc 6 theo khoảng công suất giả định.', 'source_chunk_ids': ['motor-source']}
                for option in context['required_power_scenarios']
            ]}})
    candidates = [{'code': code, 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất ' + power + ': → Loại khác'}
        for code, power in [('85015229', 'trên 1 kW nhưng không quá 37,5 kW'), ('85015239', 'trên 37,5 kW nhưng không quá 75 kW'), ('85015390', 'trên 75 kW')]]
    ai = MotorProvider()
    result = asyncio.run(ai.classifyProduct('SYNCHRONOUS SERVO MOTOR, MODEL: TVF225M-8-45-152', candidates,
        [{'chunk_id': 'motor-source', 'content': '85.01 - Động cơ điện và máy phát điện'}]))
    assert ai.calls == 2
    assert {h['code'] for h in result['legal_analysis']['hypotheses']} == {'85015229', '85015239', '85015390'}


def test_motor_power_options_keep_stated_ratings_and_phase():
    from app.ai_client import motor_power_options
    candidates = [{'code': '85015239', 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất trên 37,5 kW nhưng không quá 75 kW: → Loại khác'}]
    assert not motor_power_options('SYNCHRONOUS SERVO MOTOR, rated power: 45 kW', candidates)
    assert not motor_power_options('SYNCHRONOUS SERVO MOTOR, single-phase', candidates)
    assert not motor_power_options('Máy phát điện xoay chiều, 45 kVA', candidates)


def test_retries_an_invalid_json_response_once():
    class RetryProvider(FakeProvider):
        attempts = 0
        async def chat(self, messages):
            self.attempts += 1
            return '{"legal_analysis":' if self.attempts == 1 else '{"legal_analysis":{"hypotheses":[]}}'
    provider = RetryProvider()
    result = asyncio.run(provider.chat_json([{'role': 'user', 'content': 'Product'}]))
    assert provider.attempts == 2
    assert result['legal_analysis']['hypotheses'] == []

def test_gemini_native_adapter_uses_json_and_1536_embeddings(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-key')
    monkeypatch.setenv('AI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta')
    monkeypatch.setenv('AI_CHAT_MODEL', 'gemini-flash-latest')
    monkeypatch.setenv('AI_EMBEDDING_MODEL', 'gemini-embedding-001')
    monkeypatch.setenv('AI_EMBEDDING_DIMENSIONS', '1536')
    adapter = GeminiProvider()
    calls = []
    async def fake_post(route, body, client=None):
        calls.append((route, body))
        if route.endswith(':generateContent'):
            return {'candidates': [{'content': {'parts': [{'text': '{"status":"INSUFFICIENT_EVIDENCE"}'}]}}]}
        return {'embedding': {'values': [1.0] * 1536}}
    monkeypatch.setattr(adapter, '_post', fake_post)
    answer = asyncio.run(adapter.chat([{'role': 'system', 'content': 'Rules'}, {'role': 'user', 'content': 'Product'}]))
    vectors = asyncio.run(adapter.embed(['Product'], task_type='RETRIEVAL_QUERY'))
    assert answer == '{"status":"INSUFFICIENT_EVIDENCE"}'
    assert calls[0][1]['generationConfig']['responseMimeType'] == 'application/json'
    assert calls[0][1]['systemInstruction']['parts'][0]['text'] == 'Rules'
    assert calls[1][1]['outputDimensionality'] == 1536
    assert calls[1][1]['taskType'] == 'RETRIEVAL_QUERY'
    assert len(vectors[0]) == 1536
    assert math.isclose(sum(value * value for value in vectors[0]), 1.0)

def test_gemini_retries_temporary_503(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-key')
    adapter = GeminiProvider()
    attempts = []
    def handler(request):
        attempts.append(request)
        return httpx.Response(503 if len(attempts) == 1 else 200, json={} if len(attempts) == 1 else {'ok': True})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await adapter._post('models/test:generateContent', {}, client)
    assert asyncio.run(run()) == {'ok': True}
    assert len(attempts) == 2


def test_gemini_document_embeddings_use_batches_and_preserve_order(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-key')
    monkeypatch.setenv('AI_EMBEDDING_DIMENSIONS', '1536')
    adapter = GeminiProvider()
    calls = []
    async def post(route, body, client=None):
        calls.append((route, body))
        return {'embeddings': [{'values': [1.0] + [0.0] * 1535}, {'values': [0.0, 1.0] + [0.0] * 1534}]}
    monkeypatch.setattr(adapter, '_post', post)
    result = asyncio.run(adapter.embed(['First', 'Second'], task_type='RETRIEVAL_DOCUMENT'))
    assert calls[0][0].endswith(':batchEmbedContents')
    assert [r['content']['parts'][0]['text'] for r in calls[0][1]['requests']] == ['First', 'Second']
    assert all(r['outputDimensionality'] == 1536 and r['taskType'] == 'RETRIEVAL_DOCUMENT' for r in calls[0][1]['requests'])
    assert result[0][0] == 1 and result[1][1] == 1
