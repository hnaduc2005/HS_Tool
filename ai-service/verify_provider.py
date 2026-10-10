"""Verify configured chat and embedding APIs without printing credentials or responses."""
import asyncio
import json
import sys
import httpx
from app import config  # noqa: F401: loads root .env
from app.ai_client import provider, ChatFallbackProvider

async def main() -> None:
    ai = provider()
    if '--fallback' in sys.argv:
        if not isinstance(ai, ChatFallbackProvider):
            raise SystemExit('Configure AI_FALLBACK_PROVIDER first')
        ai = ai.fallback
    if '--simulate-chat-quota' in sys.argv:
        if not isinstance(ai, ChatFallbackProvider):
            raise SystemExit('Configure AI_FALLBACK_PROVIDER first')
        async def exhausted(_messages):
            request = httpx.Request('POST', 'https://example.test/simulated-chat-quota')
            raise httpx.HTTPStatusError('Simulated quota', request=request,
                response=httpx.Response(429, request=request, headers={'retry-after': '1'}))
        ai.primary.chat = exhausted
    try:
        answer = await ai.chat_json([
            {'role': 'system', 'content': 'Reply with a JSON object containing only the boolean key ok.'},
            {'role': 'user', 'content': 'Set ok to true.'},
        ])
        if answer.get('ok') is not True: raise ValueError('Invalid chat JSON response')
        print(f'Chat API: OK ({getattr(ai, "active_chat_provider", getattr(ai, "provider_name", "primary"))})')
        active = ai.fallback if isinstance(ai, ChatFallbackProvider) and ai.active_chat_provider == 'openrouter' else ai
        if getattr(active, 'last_model', None):
            print(f'OpenRouter model: {active.last_model}; cost: {active.last_cost}')
        if '--fallback' in sys.argv or '--simulate-chat-quota' in sys.argv:
            return
        vector = (await ai.embed(['Kiểm tra kết nối embedding'], task_type='RETRIEVAL_QUERY'))[0]
        print(f'Embedding API: OK ({len(vector)} dimensions)')
        if '--classification' in sys.argv:
            result = await ai.classifyProduct(
                'Áo phông nam 100% cotton, dệt kim',
                [{'code': '61091010', 'description': 'DEMO DATA: Áo phông dệt kim từ bông cho nam'}],
                [{'chunk_id': 'demo-chunk', 'document_id': 'demo-doc', 'title': 'DEMO DATA', 'page': None,
                  'content': 'DEMO DATA: áo phông nam từ bông, dệt kim; ứng viên minh họa 61091010.'}],
            )
            if result.get('status') not in ('COMPLETED', 'INSUFFICIENT_EVIDENCE'):
                raise ValueError('Invalid classification status')
            print('Classification JSON: OK')
    except httpx.HTTPStatusError as error:
        # Provider error bodies can echo prompts or credentials. Print status only.
        print(f'AI API rejected request: HTTP {error.response.status_code}')
        raise SystemExit(1) from None
    except (httpx.RequestError, ValueError, KeyError, IndexError) as error:
        print(f'AI API check failed: {type(error).__name__}')
        raise SystemExit(1) from None

if __name__ == '__main__':
    asyncio.run(main())
