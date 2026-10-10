import asyncio
import httpx
from pathlib import Path
from app import rag

class FakeCursor:
    def __init__(self, fetches=None): self.commands = []; self.fetches = fetches or []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def execute(self, sql, params=None): self.commands.append((sql, params))
    async def fetchone(self): return {'total': 1}
    async def fetchall(self): return self.fetches.pop(0)

class FakeConnection:
    def __init__(self, cursor): self.current = cursor
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def cursor(self): return self.current

class FakeProvider:
    async def embed(self, texts, task_type='SEMANTIC_SIMILARITY'): return [[0.1] * 1536 for _ in texts]

def test_index_document_persists_vector_and_metadata(monkeypatch):
    cursor = FakeCursor()
    async def connect(*args, **kwargs): return FakeConnection(cursor)
    monkeypatch.setattr(rag.psycopg.AsyncConnection, 'connect', connect)
    monkeypatch.setattr(rag, 'database_url', lambda: 'postgresql://test')
    path = Path(__file__).parent / 'fixtures/sample.txt'
    count = asyncio.run(rag.index_document('00000000-0000-0000-0000-000000000001', path, FakeProvider()))
    assert count > 0
    assert any('DELETE FROM document_chunks' in sql for sql, _ in cursor.commands)
    inserts = [params for sql, params in cursor.commands if 'INSERT INTO document_chunks' in sql]
    assert len(inserts) == count
    assert inserts[0][5].startswith('[0.1,0.1')
    assert 'sample.txt' in inserts[0][6]

def test_vector_and_keyword_results_are_merged(monkeypatch):
    row = {'id': 'chunk-1', 'document_id': 'doc-1', 'content': 'Máy lọc nước gia đình', 'page': 2, 'title': 'Nguồn thử', 'semantic_score': .92, 'keyword_score': .1}
    cursor = FakeCursor(fetches=[[row], [{**row, 'semantic_score': 0, 'keyword_score': .85}], [], []])
    async def connect(*args, **kwargs): return FakeConnection(cursor)
    monkeypatch.setattr(rag.psycopg.AsyncConnection, 'connect', connect)
    monkeypatch.setattr(rag, 'database_url', lambda: 'postgresql://test')
    result = asyncio.run(rag.retrieve('Máy lọc nước gia đình', FakeProvider()))
    assert len(result) == 1
    assert result[0]['semantic_score'] == .92
    assert result[0]['keyword_score'] == .85
    assert result[0]['rerank_score'] > .5


def test_heading_lookup_adds_legal_text_without_embeddings(monkeypatch):
    row = {'id': 'legal-16', 'document_id': 'doc-1', 'content': 'Chú giải 2 Chương 16: trên 20% thịt hoặc tôm.',
           'page': 178, 'title': 'Chú giải HS 2022', 'semantic_score': 0, 'keyword_score': .7,
           'metadata': {'hs_chapter': '16', 'legal_kind': 'chapter_note'}}
    cursor = FakeCursor(fetches=[[], [], [], [], [row], [], []])
    async def connect(*args, **kwargs): return FakeConnection(cursor)
    monkeypatch.setattr(rag.psycopg.AsyncConnection, 'connect', connect)
    monkeypatch.setattr(rag, 'database_url', lambda: 'postgresql://test')
    result = asyncio.run(rag.retrieve('Cơm chiên có tôm và thịt', FakeProvider(), [{'code': '16052990', 'score': .9}]))
    assert result[0]['id'] == 'legal-16'
    guided_query = next(params for sql, params in cursor.commands if "hs_heading'=ANY" in sql)
    assert guided_query[1] == ['1605']
    assert guided_query[2] == ['16']


def test_text_lookup_recovers_a_valve_heading_with_stale_metadata(monkeypatch):
    row = {'id': 'valves', 'document_id': 'doc-1', 'content': '84.81. - Vòi, van. 8481.20 - Van truyền động khí nén.',
           'page': 1951, 'title': 'Chú giải HS', 'semantic_score': 0, 'keyword_score': .7,
           'metadata': {'hs_heading': '8480', 'legal_kind': 'heading'}}
    cursor = FakeCursor(fetches=[[], [], [], [row], [], [], []])
    async def connect(*args, **kwargs): return FakeConnection(cursor)
    monkeypatch.setattr(rag.psycopg.AsyncConnection, 'connect', connect)
    monkeypatch.setattr(rag, 'database_url', lambda: 'postgresql://test')
    result = asyncio.run(rag.retrieve('PNEUMATIC VALVE φ350', FakeProvider(), [{'code': '84812090', 'score': .9}]))
    assert result[0]['id'] == 'valves'
    assert result[0]['metadata']['retrieval_heading'] == '8481'


def test_embedding_quota_does_not_discard_actual_legal_text(monkeypatch):
    row = {'id': 'real-source', 'document_id': 'doc-1', 'content': 'Máy lọc nước gia đình',
           'page': 2, 'title': 'Nguồn pháp lý', 'semantic_score': 0, 'keyword_score': .85}
    cursor = FakeCursor(fetches=[[row], [], []])
    async def connect(*args, **kwargs): return FakeConnection(cursor)
    class QuotaProvider:
        async def embed(self, *_args, **_kwargs):
            request = httpx.Request('POST', 'https://example.test/embedding')
            raise httpx.HTTPStatusError('quota', request=request, response=httpx.Response(429, request=request))
    monkeypatch.setattr(rag.psycopg.AsyncConnection, 'connect', connect)
    monkeypatch.setattr(rag, 'database_url', lambda: 'postgresql://test')
    result = asyncio.run(rag.retrieve('Máy lọc nước gia đình', QuotaProvider()))
    assert result[0]['id'] == 'real-source' and result[0]['page'] == 2
    assert not any('<=>' in sql for sql, _ in cursor.commands)
