"""Normalize the existing corpus in place while preserving chunk IDs and content.

--apply writes the search representation and repaired context. --embed also
rebuilds missing/stale semantic vectors through the app's configured provider.
Each embedding batch is committed, so an interrupted run can resume.
"""
import argparse
import asyncio
import gzip
import json
import sys
import selectors
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re
import psycopg
import httpx
from psycopg.rows import dict_row

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ai-service'))
from app.config import database_url
from app.document_normalization import normalized_chunk, embedding_text, NORMALIZATION_VERSION


async def rebuild_vectors(batch_size: int = 30, requests_per_minute: int = 90, document_ids: list[str] | None = None):
    from app.ai_client import provider
    from app.rag import vector_literal
    ai = provider()
    async with await psycopg.AsyncConnection.connect(database_url(), row_factory=dict_row) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT c.id::text,c.content,c.metadata FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='READY' AND d.title NOT ILIKE '%%DEMO DATA%%' AND c.search_text<>'' AND (%s::uuid[] IS NULL OR c.document_id=ANY(%s::uuid[])) AND (c.embedding IS NULL OR COALESCE(c.metadata->>'embedding_normalization_version','')<>%s) ORDER BY CASE WHEN c.metadata->>'legal_kind'='general_rule' THEN 0 WHEN c.metadata->>'hs_heading' IN ('8447','8481','8501','8504','6115','6215') THEN 1 WHEN c.metadata->>'legal_kind' IN ('chapter_note','section_note') THEN 2 ELSE 3 END,c.document_id,c.chunk_index", (document_ids or None, document_ids or None, str(NORMALIZATION_VERSION)))
            rows = await cursor.fetchall()
    total = len(rows)
    progress_path = root / '.logs' / 'legal-normalization' / 'embedding-progress.json'
    def progress(completed):
        report = {'embedded_this_run': completed, 'total_this_run': total, 'remaining_this_run': total - completed,
                  'status': 'complete' if completed == total else 'running',
                  'updated_at': datetime.now(timezone.utc).isoformat()}
        progress_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
    progress(0)
    for start in range(0, total, batch_size):
        batch = rows[start:start + batch_size]
        started = asyncio.get_running_loop().time()
        vectors = await ai.embed([embedding_text(row['content'], row['metadata']) for row in batch], task_type='RETRIEVAL_DOCUMENT')
        if len(vectors) != len(batch):
            raise ValueError('Embedding batch length mismatch')
        updates = [(vector_literal(vector), json.dumps({'embedding_normalization_version': NORMALIZATION_VERSION}), row['id']) for row, vector in zip(batch, vectors)]
        # Do not hold a database connection while waiting on the embedding quota.
        # Retrying a lost commit is safe because the updates are idempotent.
        for attempt in range(4):
            try:
                async with await psycopg.AsyncConnection.connect(database_url(), connect_timeout=10) as connection:
                    async with connection.cursor() as cursor:
                        await cursor.executemany("UPDATE document_chunks SET embedding=%s::vector,metadata=metadata || %s::jsonb WHERE id=%s", updates)
                break
            except psycopg.OperationalError:
                if attempt == 3: raise
                print(json.dumps({'database_retry': attempt + 1}), flush=True)
                await asyncio.sleep(2 ** attempt)
        progress(min(start + batch_size, total))
        if start + batch_size < total:
            await asyncio.sleep(max(0, len(batch) * 60 / requests_per_minute - (asyncio.get_running_loop().time() - started)))


def quota_reset_delay(response: httpx.Response) -> float | None:
    error = response.json().get('error', {})
    details = error.get('details', [])
    daily = any('perday' in str(v.get('quotaId', '')).casefold() or 'per_day' in str(v.get('quotaId', '')).casefold()
                for detail in details if isinstance(detail, dict) for v in detail.get('violations', []))
    if not daily: return None
    for detail in details:
        if isinstance(detail, dict) and str(detail.get('@type', '')).endswith('RetryInfo'):
            match = re.fullmatch(r'(\d+(?:\.\d+)?)s', str(detail.get('retryDelay', '')))
            if match: return float(match[1]) + 60
    match = re.search(r'Please retry in\s+(?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s', error.get('message', ''))
    return (float(match[1] or 0) * 3600 + float(match[2] or 0) * 60 + float(match[3]) + 60) if match else None


async def run_vectors(args):
    while True:
        try:
            await rebuild_vectors(args.batch_size, args.requests_per_minute, args.document_id)
            return
        except httpx.HTTPStatusError as error:
            delay = quota_reset_delay(error.response) if error.response.status_code == 429 else None
            if not args.resume_daily or delay is None: raise
            progress_path = root / '.logs' / 'legal-normalization' / 'embedding-progress.json'
            report = json.loads(progress_path.read_text(encoding='utf-8'))
            report.update({'status': 'waiting_quota', 'next_retry_at': (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
                           'approved_document_ids': args.document_id})
            progress_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report), flush=True)
            await asyncio.sleep(delay)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--embed', action='store_true')
    parser.add_argument('--embed-only', action='store_true', help='Resume vectors after normalization was already applied')
    parser.add_argument('--batch-size', type=int, default=30)
    parser.add_argument('--requests-per-minute', type=int, default=90)
    parser.add_argument('--resume-daily', action='store_true', help='Wait for the provider daily quota reset and continue automatically')
    parser.add_argument('--document-id', action='append', default=[], help='Restrict embeddings to explicitly authorized document IDs')
    args = parser.parse_args()
    if args.embed and not args.apply:
        parser.error('--embed requires --apply')
    if not 1 <= args.batch_size <= 64 or args.requests_per_minute <= 0:
        parser.error('batch-size must be 1..64 and requests-per-minute must be positive')
    if args.embed_only:
        try:
            asyncio.run(run_vectors(args), loop_factory=(lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())) if sys.platform == 'win32' else None)
        except httpx.HTTPStatusError as error:
            detail = error.response.json().get('error', {}).get('message', 'Embedding request failed')
            print(json.dumps({'embedding_error_status': error.response.status_code, 'message': detail}), flush=True)
            raise SystemExit(1)
        return
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        rows = connection.execute("SELECT c.id::text,c.document_id::text,c.content,c.page,c.chunk_index,c.metadata FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='READY' ORDER BY c.document_id,c.chunk_index").fetchall()
        context = {}
        changes = []
        repaired = 0
        for row in rows:
            text, metadata, inherited = normalized_chunk(row['content'], row['metadata'], context.get(row['document_id'], {}))
            context[row['document_id']] = inherited
            if any(metadata.get(key) != row['metadata'].get(key) for key in ('hs_heading', 'hs_chapter', 'hs_section')):
                repaired += 1
            changes.append((text, json.dumps(metadata, ensure_ascii=False), row['id']))
        summary = {'chunks': len(rows), 'documents': len(context), 'repaired_context': repaired, 'normalization_version': NORMALIZATION_VERSION, 'applied': args.apply}
        if args.apply:
            directory = root / '.logs' / 'legal-normalization'
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / ('backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json.gz')
            with gzip.open(target, 'wt', encoding='utf-8') as archive:
                json.dump(rows, archive, ensure_ascii=False, default=str)
            connection.execute((root / 'backend/prisma/migrations/20261008000000_searchable_legal_text/migration.sql').read_text(encoding='utf-8'))
            with connection.cursor() as cursor:
                cursor.executemany('UPDATE document_chunks SET search_text=%s,metadata=%s::jsonb WHERE id=%s', changes)
            connection.commit()
            (directory / 'normalization-report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            summary['backup'] = str(target.relative_to(root))
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.embed:
        try:
            asyncio.run(run_vectors(args), loop_factory=(lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())) if sys.platform == 'win32' else None)
        except httpx.HTTPStatusError as error:
            detail = error.response.json().get('error', {}).get('message', 'Embedding request failed')
            print(json.dumps({'embedding_error_status': error.response.status_code, 'message': detail}), flush=True)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
