import asyncio
import json

import httpx
import pytest

from app import ai_client
from app.ai_client import ChatFallbackProvider, OpenRouterFreeProvider, free_openrouter_model, provider


def model(name='openrouter/free', **overrides):
    return {'id': name, 'pricing': {'prompt': '0', 'completion': '0'},
            'supported_parameters': ['response_format', 'temperature', 'max_tokens'], **overrides}


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('AI_API_KEY', 'primary-test-key')
    monkeypatch.setenv('AI_BASE_URL', 'https://primary.test/v1beta')
    monkeypatch.setenv('AI_CHAT_MODEL', 'test-chat')
    monkeypatch.setenv('AI_EMBEDDING_MODEL', 'test-embedding')
    monkeypatch.setenv('AI_EMBEDDING_DIMENSIONS', '1536')
    monkeypatch.setenv('AI_FALLBACK_PROVIDER', 'openrouter')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'openrouter-test-key')
    monkeypatch.setenv('OPENROUTER_BASE_URL', 'https://openrouter.test/api/v1')
    monkeypatch.setenv('OPENROUTER_CHAT_MODEL', 'openrouter/free')
    ChatFallbackProvider._quota_until.clear()
    OpenRouterFreeProvider._models_cache.clear()
    yield
    ChatFallbackProvider._quota_until.clear()
    OpenRouterFreeProvider._models_cache.clear()


def transport(monkeypatch, respond):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(ai_client.httpx, 'AsyncClient', lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))


def completion(content='{"ok":true}', **overrides):
    return {'model': 'test/model:free', 'usage': {'cost': 0},
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}], **overrides}


@pytest.mark.parametrize('row', [
    model('paid/model', pricing={'prompt': '0.001', 'completion': '0.002'}),
    model('fake/model:free', pricing={'prompt': '0', 'completion': '0.01'}),
    model('free-with-fee:free', pricing={'prompt': '0', 'completion': '0', 'request': '0.1'}),
    model('free/model:free', pricing={'prompt': '0'}),
    model('free/model:free', pricing={'prompt': 'NaN', 'completion': '0'}),
    model('free/model:free', pricing={'prompt': '-1', 'completion': '0'}),
    model('free/model:free', pricing={'prompt': None, 'completion': '0'}),
    {'id': 'free/model:free'}, None,
])
def test_only_verified_zero_priced_free_variants_are_allowed(row):
    assert free_openrouter_model(row) is False
    assert free_openrouter_model(model()) is True
    assert free_openrouter_model(model('actual/model:free')) is True


@pytest.mark.parametrize('name', ['openrouter/auto', 'provider/paid-model', 'provider/model:free:nitro', ''])
def test_paid_and_auto_routes_are_rejected_before_network(monkeypatch, name):
    monkeypatch.setenv('OPENROUTER_CHAT_MODEL', name)
    with pytest.raises(ValueError, match='only'):
        OpenRouterFreeProvider()


def test_openrouter_factory_and_missing_key(monkeypatch):
    ai = provider()
    assert isinstance(ai, ChatFallbackProvider) and isinstance(ai.fallback, OpenRouterFreeProvider)
    assert ai.primary.chat_quota_fallback is True
    monkeypatch.setenv('OPENROUTER_API_KEY', '')
    with pytest.raises(RuntimeError, match='OPENROUTER_API_KEY'):
        provider()


def test_real_http_quota_path_keeps_json_and_zero_price_guard(monkeypatch):
    requests = []
    messages = [{'role': 'system', 'content': 'Return JSON'}, {'role': 'user', 'content': 'Set ok to true'}]
    def respond(request):
        requests.append(request)
        if request.url.host == 'primary.test':
            return httpx.Response(429, headers={'retry-after': '43'})
        assert request.headers['authorization'] == 'Bearer openrouter-test-key'
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [model(), model('paid/model', pricing={'prompt': '1', 'completion': '1'})]})
        body = json.loads(request.content)
        assert body['messages'] == messages
        assert body['model'] == 'openrouter/free'
        assert body['provider'] == {'require_parameters': True,
            'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0}}
        assert 'models' not in body and 'plugins' not in body
        return httpx.Response(200, json=completion())
    transport(monkeypatch, respond)
    ai = provider()
    assert asyncio.run(ai.chat_json(messages)) == {'ok': True}
    assert ai.active_chat_provider == 'openrouter' and ai.fallback.last_cost == '0'
    assert asyncio.run(ai.chat_json(messages)) == {'ok': True}
    assert len([r for r in requests if r.url.host == 'primary.test']) == 1
    assert len([r for r in requests if r.url.path.endswith('/models')]) == 1


@pytest.mark.parametrize('rows', [[], [model(pricing={'prompt': '0', 'completion': '1'})],
    [model(supported_parameters=[])], [model('other/model:free')]])
def test_missing_priced_or_non_json_model_stops_before_chat(monkeypatch, rows):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'data': rows})
    transport(monkeypatch, respond)
    with pytest.raises(ValueError, match='unavailable'):
        asyncio.run(OpenRouterFreeProvider().chat([]))
    assert len(requests) == 1 and requests[0].method == 'GET'


def test_model_catalog_refreshes_when_cache_expires(monkeypatch):
    now, calls = [100.0], []
    monkeypatch.setattr(ai_client.time, 'monotonic', lambda: now[0])
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'data': [model()] if len(calls) == 1 else []})
    transport(monkeypatch, respond)
    async def run():
        ai = OpenRouterFreeProvider()
        async with httpx.AsyncClient() as client:
            assert await ai.free_models(client) == [model()]
            assert await ai.free_models(client) == [model()]
            now[0] = 401.0
            assert await ai.free_models(client) == []
    asyncio.run(run())
    assert len(calls) == 2


@pytest.mark.parametrize('data', [completion(choices=[]), completion(content=None),
    completion(choices=[{'finish_reason': 'length', 'message': {'content': '{"ok":true}'}}]),
    completion(usage={'cost': '0.01'}), {'error': {'code': 503}}])
def test_invalid_or_nonzero_cost_result_is_rejected(monkeypatch, data):
    def respond(request):
        return httpx.Response(200, json={'data': [model()]} if request.method == 'GET' else data)
    transport(monkeypatch, respond)
    with pytest.raises(ValueError):
        asyncio.run(OpenRouterFreeProvider().chat([]))


def test_openrouter_rate_limit_does_not_fall_back_to_paid_or_deepseek(monkeypatch):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'data': [model()]}) if request.method == 'GET' else httpx.Response(429)
    transport(monkeypatch, respond)
    with pytest.raises(httpx.HTTPStatusError) as raised:
        asyncio.run(OpenRouterFreeProvider().chat([]))
    assert raised.value.response.status_code == 429
    assert len(calls) == 2 and all(r.url.host == 'openrouter.test' for r in calls)


def test_openrouter_never_generates_embeddings():
    with pytest.raises(NotImplementedError):
        asyncio.run(OpenRouterFreeProvider().embed(['source']))
