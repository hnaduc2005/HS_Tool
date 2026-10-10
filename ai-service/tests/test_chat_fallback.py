import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app import ai_client
from app.ai_client import AIProvider, ChatFallbackProvider, DeepSeekProvider, GeminiProvider, provider


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('AI_API_KEY', 'primary-test-key')
    monkeypatch.setenv('AI_BASE_URL', 'https://primary.test/v1beta')
    monkeypatch.setenv('AI_CHAT_MODEL', 'test-chat')
    monkeypatch.setenv('AI_EMBEDDING_MODEL', 'test-embedding')
    monkeypatch.setenv('AI_EMBEDDING_DIMENSIONS', '1536')
    monkeypatch.setenv('AI_FALLBACK_PROVIDER', 'deepseek')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'fallback-test-key')
    monkeypatch.setenv('DEEPSEEK_BASE_URL', 'https://fallback.test/v1')
    monkeypatch.setenv('DEEPSEEK_CHAT_MODEL', 'deepseek-flash')
    ChatFallbackProvider._quota_until.clear()
    yield
    ChatFallbackProvider._quota_until.clear()


def upstream_error(status, **kwargs):
    request = httpx.Request('POST', 'https://primary.test/chat')
    return httpx.HTTPStatusError('upstream', request=request,
        response=httpx.Response(status, request=request, **kwargs))


def test_config_is_optional_and_enables_fast_gemini_chat_fallback(monkeypatch):
    ai = provider()
    assert isinstance(ai, AIProvider) and isinstance(ai, ChatFallbackProvider)
    assert ai.primary.chat_quota_fallback is True
    monkeypatch.setenv('AI_FALLBACK_PROVIDER', '')
    plain = provider()
    assert isinstance(plain, GeminiProvider) and plain.chat_quota_fallback is False


def test_missing_fallback_key_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', '')
    with pytest.raises(RuntimeError, match='DEEPSEEK_API_KEY'):
        provider()


def test_primary_success_preserves_the_request_and_does_not_call_deepseek():
    ai = provider()
    ai.primary.chat = AsyncMock(return_value='{"ok":true}')
    ai.fallback.chat = AsyncMock()
    messages = [{'role': 'user', 'content': 'Return JSON'}]
    assert asyncio.run(ai.chat_json(messages)) == {'ok': True}
    ai.primary.chat.assert_awaited_once_with(messages)
    ai.fallback.chat.assert_not_awaited()


def test_quota_switches_every_stage_and_new_requests_until_reset(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(ai_client.time, 'monotonic', lambda: now[0])
    ai = provider()
    ai.primary.chat = AsyncMock(side_effect=upstream_error(429, headers={'retry-after': '43'}))
    ai.fallback.chat = AsyncMock(return_value='{"ok":true}')
    messages = [{'role': 'user', 'content': 'Return JSON'}]
    asyncio.run(ai.chat(messages))
    asyncio.run(ai.chat(messages))
    ai.primary.chat.assert_awaited_once_with(messages)
    assert ai.fallback.chat.await_count == 2
    second = provider()
    second.primary.chat = AsyncMock(return_value='{"ok":true}')
    second.fallback.chat = AsyncMock(return_value='{"ok":true}')
    asyncio.run(second.chat(messages))
    second.primary.chat.assert_not_awaited()
    now[0] = 144.0
    third = provider()
    third.primary.chat = AsyncMock(return_value='{"ok":true}')
    third.fallback.chat = AsyncMock()
    asyncio.run(third.chat(messages))
    third.primary.chat.assert_awaited_once_with(messages)
    third.fallback.chat.assert_not_awaited()
    # The in-progress request keeps its selected provider after the reset.
    asyncio.run(ai.chat(messages))
    assert ai.fallback.chat.await_count == 3


@pytest.mark.parametrize('status', [400, 401, 403, 500, 503])
def test_non_quota_error_is_not_hidden(status):
    ai = provider()
    ai.primary.chat = AsyncMock(side_effect=upstream_error(status))
    ai.fallback.chat = AsyncMock()
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai.chat([]))
    ai.fallback.chat.assert_not_awaited()


def test_embeddings_stay_with_primary_after_chat_switch_and_fail_honestly():
    ai = provider()
    ai.primary.chat = AsyncMock(side_effect=upstream_error(429))
    ai.fallback.chat = AsyncMock(return_value='{"ok":true}')
    ai.primary.embed = AsyncMock(return_value=[[0.1] * 1536])
    ai.fallback.embed = AsyncMock()
    asyncio.run(ai.chat([]))
    assert asyncio.run(ai.embed(['source'], task_type='RETRIEVAL_DOCUMENT')) == [[0.1] * 1536]
    ai.primary.embed.assert_awaited_once_with(['source'], task_type='RETRIEVAL_DOCUMENT')
    ai.primary.embed.side_effect = upstream_error(429)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai.embed(['source']))
    ai.fallback.embed.assert_not_awaited()


def test_gemini_chat_429_does_not_sleep_but_embedding_still_retries(monkeypatch):
    waits, routes = [], []
    async def sleep(delay): waits.append(delay)
    monkeypatch.setattr(ai_client.asyncio, 'sleep', sleep)
    def respond(request):
        routes.append(request.url.path)
        if len(routes) <= 2:
            return httpx.Response(429, headers={'retry-after': '43'})
        return httpx.Response(200, json={'ok': True})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            ai = GeminiProvider(chat_quota_fallback=True)
            with pytest.raises(httpx.HTTPStatusError):
                await ai._post('models/test:generateContent', {}, client)
            assert waits == [] and len(routes) == 1
            assert await ai._post('models/test:embedContent', {}, client) == {'ok': True}
    asyncio.run(run())
    assert waits == [43] and len(routes) == 3


def test_deepseek_endpoint_auth_json_mode_and_contract_repair(monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': 'invalid JSON' if len(requests) == 1 else '{"queries":["biến tần"],"heading_hints":["850440"]}'}}]})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(ai_client.httpx, 'AsyncClient', lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))
    result = asyncio.run(DeepSeekProvider().suggestCatalogSearch('INVERTER, MODEL: TEST'))
    assert result == {'queries': ['biến tần'], 'heading_hints': ['850440']}
    assert len(requests) == 2
    assert str(requests[0].url) == 'https://fallback.test/v1/chat/completions'
    assert requests[0].headers['authorization'] == 'Bearer fallback-test-key'
    body = json.loads(requests[0].content)
    assert body['response_format'] == {'type': 'json_object'}
    assert body['thinking'] == {'type': 'disabled'}
    assert body['model'] == 'deepseek-flash'
    assert 'user' == body['messages'][-1]['role']


@pytest.mark.parametrize('choices', [[], [{'message': {'content': None}}],
    [{'finish_reason': 'length', 'message': {'content': '{"ok":true}'}}]])
def test_deepseek_rejects_empty_or_truncated_output(monkeypatch, choices):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(ai_client.httpx, 'AsyncClient', lambda **kwargs:
        real_client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={'choices': choices})), **kwargs))
    with pytest.raises(ValueError):
        asyncio.run(DeepSeekProvider().chat([]))


def test_fallback_insufficient_balance_is_reported():
    ai = provider()
    ai.primary.chat = AsyncMock(side_effect=upstream_error(429))
    ai.fallback.chat = AsyncMock(side_effect=upstream_error(402))
    with pytest.raises(httpx.HTTPStatusError) as raised:
        asyncio.run(ai.chat([]))
    assert raised.value.response.status_code == 402


def test_quota_delay_uses_daily_reset_and_tolerates_missing_details():
    response = httpx.Response(429, json={'error': {'details': [
        {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '32400s'}]}})
    assert ai_client.quota_fallback_delay(response) == 32401
    assert ai_client.quota_fallback_delay(httpx.Response(429, json={'error': {'details': None}})) == 60
