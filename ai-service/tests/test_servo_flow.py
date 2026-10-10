"""Regression: valid model power_range hypotheses were all discarded as unknown attributes."""
import asyncio
import json
from app import rag
from app.ai_client import AIProvider


def test_servo_invoice_keeps_all_power_hypotheses_after_understanding(monkeypatch):
    description = 'HIGH EFFICIENCY PERMANENT MAGNET\nSYNCHRONOUS SERVO MOTOR, MODEL:\nTVF225M-8-45-152 WT\n8 PCS 1,929.00 15,432.00'
    candidates = [{'code': code, 'description': 'Động cơ xoay chiều khác, đa pha: → Công suất ' + power + ': → Loại khác'}
        for code, power in [('85015229', 'trên 1 kW nhưng không quá 37,5 kW'),
                            ('85015239', 'trên 37,5 kW nhưng không quá 75 kW'), ('85015390', 'trên 75 kW')]]
    async def retrieve(*args):
        return [{'id': 'motor', 'document_id': 'doc', 'content': '85.01 - Động cơ điện. Các động cơ điện là các loại máy chuyển điện năng sang cơ năng.',
                 'title': 'Chú giải', 'page': 1, 'semantic_score': .8, 'keyword_score': .8, 'rerank_score': .8}]
    monkeypatch.setattr(rag, 'retrieve', retrieve)
    class Provider(AIProvider):
        calls = 0
        async def embed(self, *args, **kwargs): return []
        async def chat(self, messages):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            if 'product_understanding' not in context:
                return json.dumps({'product_name': 'Động cơ servo đồng bộ', 'scope': 'whole',
                    'missing_attributes': ['power', 'phase', 'current_type'],
                    'identity_eligible_codes': [c['code'] for c in candidates]})
            return json.dumps({'status': 'CONDITIONAL', 'missing_information': ['Công suất chưa khai'],
                'legal_analysis': {'legal_steps': [{'rule': 'Nhóm 85.01', 'application': 'Động cơ chuyển điện năng sang cơ năng.', 'source_chunk_ids': ['motor']}],
                    'hypotheses': [{'code': option['code'], 'label': 'Khoảng công suất', 'classification_mode': 'single',
                        'assumptions': option['assumptions'], 'reasoning': 'Đối chiếu đúng khoảng công suất trong danh mục.',
                        'source_chunk_ids': ['motor'], 'assumed_attributes': [
                            {'attribute': 'power_range', 'value': option['assumptions'][1]},
                            {'attribute': 'phase_count', 'value': 'đa pha'}, {'attribute': 'current_type', 'value': 'xoay chiều'}]}
                        for option in context['required_power_scenarios']]}})
    provider = Provider()
    result = asyncio.run(rag.classify(description, candidates, provider))
    assert result['status'] == 'CONDITIONAL'
    assert {h['code'] for h in result['legal_analysis']['hypotheses']} == {c['code'] for c in candidates}
    assert provider.calls == 2
    assert all({a['attribute'] for a in h['assumed_attributes']} == {'power', 'phase', 'current_type'}
               for h in result['legal_analysis']['hypotheses'])
    assert result['sources'] and result['legal_analysis']['legal_steps']
    assert not any(fact.get('attribute') == 'power' for fact in result['legal_analysis']['product_understanding']['facts'])
