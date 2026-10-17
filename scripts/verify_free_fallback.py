"""Verify the free OpenRouter fallback using real catalog entries and legal retrieval."""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app import config  # noqa: E402, F401: loads root .env
from app.ai_client import ChatFallbackProvider, OpenRouterFreeProvider, provider  # noqa: E402
from app.rag import classify  # noqa: E402


async def main():
    ai = provider()
    if not isinstance(ai, ChatFallbackProvider) or not isinstance(ai.fallback, OpenRouterFreeProvider):
        raise ValueError('Configure the free OpenRouter fallback first')
    async def exhausted(_messages):
        request = httpx.Request('POST', 'https://example.test/simulated-chat-quota')
        raise httpx.HTTPStatusError('Simulated quota', request=request,
            response=httpx.Response(429, request=request, headers={'retry-after': '1'}))
    ai.primary.chat = exhausted
    token = os.environ.get('HS_AUTH_TOKEN')
    if not token:
        raise ValueError('Set HS_AUTH_TOKEN to a company account access token before running this check')
    async with httpx.AsyncClient(timeout=15, headers={'Authorization': f'Bearer {token}'}) as client:
        response = await client.get('http://127.0.0.1:3001/api/hs-codes/search', params={'q': '8447', 'limit': 50})
        response.raise_for_status()
        catalog = response.json()
    descriptions = {row['code']: row['description'] for row in catalog}
    # Match the backend classification input, which includes ancestor conditions.
    # The catalog search returns leaf labels for browsing.
    candidates = [{**row, 'description': ' → '.join(
        descriptions[code].lstrip('- ').strip() for code in (row['code'][:4], row['code'][:6], row['code'])
        if code in descriptions)} for row in catalog if len(row['code']) == 8]
    description = 'COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW\n230011002000MM'
    result = await classify(description, candidates, ai)
    codes = ([result['recommended_code']] if result.get('recommended_code') else [])
    codes += [row['code'] for row in result.get('candidates', []) if row['code'] not in codes]
    report = {'status': result['status'], 'codes': codes, 'chat_provider': ai.active_chat_provider,
              'last_model': ai.fallback.last_model, 'last_cost': ai.fallback.last_cost,
              'source_ids': [row['chunk_id'] for row in result.get('sources', [])],
              'primary_chat_quota_simulated': True, 'embedding_provider_changed': False}
    (ROOT / '.logs' / 'openrouter-free-classification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert report['status'] == 'COMPLETED' and codes[0] == '84479010', 'Unexpected crochet classification'
    assert report['source_ids'], 'Classification lacks actual legal references'
    assert report['last_cost'] is not None and float(report['last_cost']) == 0, 'Zero cost was not verified'
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except httpx.HTTPStatusError as error:
        print(f'Free fallback verification: HTTP {error.response.status_code}')
        raise SystemExit(1) from None
    except Exception as error:
        print(f'Free fallback verification: {type(error).__name__}')
        raise SystemExit(1) from None
