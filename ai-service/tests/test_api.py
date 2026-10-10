import os
import httpx
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app import main

def test_internal_endpoint_rejects_missing_token(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    with TestClient(app) as client:
        response = client.post('/parse-hs', json={'path': 'missing.csv'})
    assert response.status_code == 401

def test_health_check():
    with TestClient(app) as client:
        response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_product_extraction_keeps_text_beyond_old_single_product_limit(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    text = 'COMPUTERIZED CROCHET MACHINE\n' * 100 + 'MODEL: LAST-ITEM'
    monkeypatch.setattr(main, 'checked_path', lambda path: path)
    monkeypatch.setattr(main, 'extract', lambda path: [(text, None, {})])
    with TestClient(app) as client:
        response = client.post('/extract-product', headers={'x-service-token': 'test-secret'}, json={'path': 'products.txt'})
    assert response.status_code == 200
    assert response.json()['text'].endswith('MODEL: LAST-ITEM')
    assert len(response.json()['text']) > 1600


def test_product_extraction_rejects_oversize_instead_of_silently_dropping_items(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    monkeypatch.setattr(main, 'checked_path', lambda path: path)
    monkeypatch.setattr(main, 'extract', lambda path: [('a' * 20001, None, {})])
    with TestClient(app) as client:
        response = client.post('/extract-product', headers={'x-service-token': 'test-secret'}, json={'path': 'products.txt'})
    assert response.status_code == 400 and '20.000' in response.json()['detail']


def test_classification_accepts_empty_candidate_list_for_legal_review(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    async def review(description, candidates, provider):
        assert candidates == []
        return {'status': 'INSUFFICIENT_EVIDENCE', 'legal_analysis': {'summary': 'Đã đối chiếu Quy tắc 1.'}}
    monkeypatch.setattr(main, 'classify', review)
    monkeypatch.setattr(main, 'provider', lambda: object())
    with TestClient(app) as client:
        response = client.post('/classify', headers={'x-service-token': 'test-secret'},
                               json={'description': 'Kệ TV bằng gỗ ghép và ván MDF', 'candidates': []})
    assert response.status_code == 200
    assert response.json()['legal_analysis']['summary'] == 'Đã đối chiếu Quy tắc 1.'


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_provider_outage_is_not_returned_as_insufficient_evidence(monkeypatch, status):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    async def limited(*_args):
        request = httpx.Request('POST', 'https://generativelanguage.googleapis.com/v1beta/models/test:generateContent')
        response = httpx.Response(status, request=request)
        raise httpx.HTTPStatusError('quota', request=request, response=response)
    monkeypatch.setattr(main, 'classify', limited)
    with TestClient(app) as client:
        response = client.post('/classify', headers={'x-service-token': 'test-secret'}, json={
            'description': 'Cơm chiên hộp kín khí: gạo 55%; tôm 11%; thịt lợn 10%; cà rốt 5%; hành tây 5%; gia vị 4%',
            'candidates': [{'code': '16052990', 'description': 'Loại khác'}],
        })
    assert response.status_code == 503
    assert response.json() == {'detail': 'AI_SERVICE_UNAVAILABLE'}


def test_blocked_outbound_connection_reports_service_error(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    async def blocked(*_args):
        raise httpx.ConnectError('connection blocked')
    monkeypatch.setattr(main, 'classify', blocked)
    with TestClient(app) as client:
        response = client.post('/classify', headers={'x-service-token': 'test-secret'},
                               json={'description': 'Kệ TV bằng gỗ ghép và ván MDF', 'candidates': []})
    assert response.status_code == 503
    assert response.json() == {'detail': 'AI_SERVICE_UNAVAILABLE'}


def test_unexpected_error_logs_frames_without_error_content(monkeypatch, caplog):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    monkeypatch.setattr(main, 'provider', lambda: object())
    async def malformed(*_args):
        raise TypeError('private product text and credential must not appear')
    monkeypatch.setattr(main, 'classify', malformed)
    with TestClient(app) as client:
        response = client.post('/classify', headers={'x-service-token': 'test-secret'},
            json={'description': 'Example product for error handling', 'candidates': []})
    assert response.status_code == 503
    assert 'TypeError; frames=' in caplog.text and 'malformed' in caplog.text
    assert 'private product text' not in caplog.text and 'credential' not in caplog.text


def test_readiness_requires_token(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    with TestClient(app) as client:
        assert client.get('/ready').status_code == 401


def test_liveness_does_not_mask_blocked_ai_readiness(monkeypatch):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    class BlockedProvider:
        async def chat(self, *_args):
            raise httpx.ConnectError('blocked')
    monkeypatch.setattr(main, 'provider', BlockedProvider)
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        response = client.get('/ready', headers={'x-service-token': 'test-secret'})
    assert response.status_code == 503
    assert response.json() == {'detail': 'AI_SERVICE_UNAVAILABLE'}


@pytest.mark.parametrize('has_catalog', [True, False])
@pytest.mark.parametrize('embedding_quota', [True, False])
def test_readiness_checks_ai_and_database_contents(monkeypatch, has_catalog, embedding_quota):
    monkeypatch.setenv('AI_SERVICE_TOKEN', 'test-secret')
    class WorkingProvider:
        chat = AsyncMock(return_value='{"ok": true}')
        embed = AsyncMock(return_value=[[0.1] * 1536])
    if embedding_quota:
        request = httpx.Request('POST', 'https://example.test/embedding')
        WorkingProvider.embed.side_effect = httpx.HTTPStatusError('quota', request=request, response=httpx.Response(429, request=request))
    class Cursor:
        execute = AsyncMock()
        fetchone = AsyncMock(side_effect=[(1,), (1,)] if has_catalog else [None])
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
    cursor = Cursor()
    class Connection:
        def cursor(self): return cursor
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
    connect = AsyncMock(return_value=Connection())
    monkeypatch.setattr(main, 'provider', WorkingProvider)
    monkeypatch.setattr(main, 'database_url', lambda: 'postgresql://test')
    monkeypatch.setattr(main.psycopg.AsyncConnection, 'connect', connect)
    with TestClient(app) as client:
        response = client.get('/ready', headers={'x-service-token': 'test-secret'})
    WorkingProvider.chat.assert_awaited_once()
    WorkingProvider.embed.assert_awaited_once()
    connect.assert_awaited_once()
    assert response.status_code == (200 if has_catalog else 503)
    if has_catalog:
        assert response.json() == {'status': 'ready', 'chat': 'ok', 'embedding': 'temporarily_unavailable' if embedding_quota else 'ok', 'database': 'ok', 'retrieval': 'keyword_and_legal_context' if embedding_quota else 'semantic_and_keyword'}
