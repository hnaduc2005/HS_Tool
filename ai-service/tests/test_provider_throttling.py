import asyncio
import httpx
import pytest
from app.ai_client import GeminiProvider, provider_retry_delay
from app.document_parser import clean


def test_retry_info_preserves_the_server_wait():
    response = httpx.Response(429, json={'error': {'details': [
        {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '43.264891648s'}]}})
    assert provider_retry_delay(response, 0) == pytest.approx(44.264891648)


def test_daily_quota_is_not_treated_as_a_temporary_throttle():
    response = httpx.Response(429, json={'error': {'details': [
        {'violations': [{'quotaId': 'EmbedContentRequestsPerDayPerProjectPerModel-FreeTier'}]},
        {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '43s'}]}})
    assert provider_retry_delay(response, 0) is None


def test_retry_uses_retry_info_and_preserves_the_request(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-key')
    waits, bodies = [], []
    async def sleep(delay): waits.append(delay)
    monkeypatch.setattr('app.ai_client.asyncio.sleep', sleep)
    def respond(request):
        bodies.append(request.content)
        if len(bodies) == 1:
            return httpx.Response(429, json={'error': {'details': [
                {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '43s'}]}})
        return httpx.Response(200, json={'ok': True})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            assert await GeminiProvider()._post('models/test:embedContent', {'content': 'definition'}, client) == {'ok': True}
    asyncio.run(run())
    assert waits == [44]
    assert len(bodies) == 2 and bodies[0] == bodies[1]


def test_import_preserves_legal_units_and_removes_soft_breaks():
    assert clean('Dưới 1.500 cm³; ≤ 5 kW; thép không\u00ad gỉ') == 'Dưới 1.500 cm³; ≤ 5 kW; thép không gỉ'
