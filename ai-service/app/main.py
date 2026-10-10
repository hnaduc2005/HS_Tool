import logging
import json
import traceback
import httpx
import psycopg
from uuid import UUID
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .ai_client import provider
from .config import checked_path, database_url
from .document_parser import parse_hs, extract, clean
from .rag import classify, index_document
from .product_batch import prepare_batch

app = FastAPI(title='HS AI internal service', docs_url=None, redoc_url=None)
logger = logging.getLogger('hs-ai')

def internal(x_service_token: str | None = Header(default=None)):
    import os
    expected = os.getenv('AI_SERVICE_TOKEN', '')
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=401, detail='Unauthorized')

class Candidate(BaseModel):
    code: str
    description: str
    score: float | None = None
class ClassifyRequest(BaseModel):
    description: str = Field(min_length=2, max_length=2000)
    candidates: list[Candidate] = Field(max_length=50)
class DiscoverRequest(BaseModel):
    description: str = Field(min_length=2, max_length=2000)
class BatchRequest(BaseModel):
    description: str = Field(min_length=2, max_length=20000)
class IndexRequest(BaseModel):
    document_id: UUID
    path: str
class ParseRequest(BaseModel):
    path: str

@app.get('/health')
def health(): return {'status': 'ok'}

@app.get('/ready', dependencies=[Depends(internal)])
async def ready():
    """Check dependencies from this process, including its outbound network access."""
    try:
        ai = provider()
        answer = await ai.chat([
            {'role': 'system', 'content': 'Reply with a JSON object containing only the boolean key ok.'},
            {'role': 'user', 'content': 'Set ok to true.'},
        ])
        if json.loads(answer).get('ok') is not True:
            raise ValueError('Invalid chat response')
        embedding_status = 'ok'
        try:
            vectors = await ai.embed(['Kiểm tra kết nối embedding'], task_type='RETRIEVAL_QUERY')
            if len(vectors) != 1 or len(vectors[0]) != 1536:
                raise ValueError('Invalid embedding response')
        except (httpx.RequestError, httpx.HTTPStatusError) as error:
            if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in (429, 500, 502, 503, 504):
                raise
            embedding_status = 'temporarily_unavailable'
        async with await psycopg.AsyncConnection.connect(database_url(), connect_timeout=8) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT 1 FROM hs_codes WHERE is_active=true LIMIT 1')
                if not await cursor.fetchone():
                    raise ValueError('HS catalog is empty')
                await cursor.execute("SELECT 1 FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='READY' AND d.title NOT ILIKE '%DEMO DATA%' AND d.source NOT ILIKE '%minh họa%' LIMIT 1")
                if not await cursor.fetchone():
                    raise ValueError('Legal corpus is empty')
        return {'status': 'ready', 'chat': 'ok', 'embedding': embedding_status, 'database': 'ok',
                'retrieval': 'semantic_and_keyword' if embedding_status == 'ok' else 'keyword_and_legal_context'}
    except Exception as error:
        logger.error('Readiness check failed: %s', type(error).__name__)
        raise HTTPException(status_code=503, detail='AI_SERVICE_UNAVAILABLE') from error

@app.post('/discover-candidates', dependencies=[Depends(internal)])
async def discover_candidates_route(body: DiscoverRequest):
    try:
        return await provider().suggestCatalogSearch(body.description)
    except (httpx.RequestError, httpx.HTTPStatusError) as error:
        logger.error('Candidate discovery failed: upstream %s', type(error).__name__)
        raise HTTPException(status_code=503, detail='AI_SERVICE_UNAVAILABLE') from error

@app.post('/classify', dependencies=[Depends(internal)])
async def classify_route(body: ClassifyRequest):
    try:
        return await classify(body.description, [c.model_dump() for c in body.candidates], provider())
    except Exception as error:
        if isinstance(error, httpx.HTTPStatusError):
            logger.error('Classification failed: upstream %s HTTP %s', error.request.url.path, error.response.status_code)
        elif isinstance(error, httpx.RequestError):
            logger.error('Classification failed: upstream unavailable')
        else:
            frames = ' -> '.join(f'{frame.filename}:{frame.lineno}:{frame.name}'
                                 for frame in traceback.extract_tb(error.__traceback__))
            logger.error('Classification failed: %s; frames=%s', type(error).__name__, frames)
        raise HTTPException(status_code=503, detail='AI_SERVICE_UNAVAILABLE') from error

@app.post('/prepare-items', dependencies=[Depends(internal)])
async def prepare_items_route(body: BatchRequest):
    try:
        return await prepare_batch(body.description, provider())
    except Exception as error:
        logger.error('Item separation failed: %s', type(error).__name__)
        raise HTTPException(status_code=503, detail='AI_SERVICE_UNAVAILABLE') from error

@app.post('/index-document', dependencies=[Depends(internal)])
async def index_route(body: IndexRequest):
    try:
        count = await index_document(str(body.document_id), checked_path(body.path), provider())
        return {'indexed_chunks': count}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.error('Indexing failed: %s', type(error).__name__)
        raise HTTPException(status_code=503, detail='INDEXING_FAILED') from error

@app.post('/parse-hs', dependencies=[Depends(internal)])
def parse_hs_route(body: ParseRequest):
    try: return {'rows': parse_hs(checked_path(body.path))}
    except ValueError as error: raise HTTPException(status_code=400, detail=str(error)) from error

@app.post('/extract-product', dependencies=[Depends(internal)])
def extract_product_route(body: ParseRequest):
    try:
        path = checked_path(body.path)
        parts = []
        length = 0
        for content, _, _ in extract(path):
            length += len(content) + 1
            if length > 20000:
                raise ValueError('Tài liệu sản phẩm vượt 20.000 ký tự. Hãy chia tài liệu thành các lượt nhỏ hơn để giữ đủ thông tin từng mặt hàng.')
            parts.append(content)
        text = '\n'.join(parts)
        if not text.strip(): raise ValueError('No extractable text')
        return {'text': clean(text)}
    except ValueError as error: raise HTTPException(status_code=400, detail=str(error)) from error
