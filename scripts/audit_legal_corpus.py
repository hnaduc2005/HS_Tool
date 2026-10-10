"""Read-only integrity audit against the original normalization backup."""
import gzip
import json
import sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ai-service'))
from app.config import database_url
from app.document_normalization import NORMALIZATION_VERSION

sys.stdout.reconfigure(encoding='utf-8')
directory = root / '.logs' / 'legal-normalization'
baseline_path = sorted(directory.glob('backup-*.json.gz'))[0]
with gzip.open(baseline_path, 'rt', encoding='utf-8') as archive:
    baseline = {row['id']: row for row in json.load(archive)}
with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=10) as connection:
    rows = connection.execute("SELECT c.id::text,c.document_id::text,c.content,c.page,c.chunk_index,c.metadata,c.search_text,c.embedding IS NOT NULL AS embedded,d.title FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='READY'").fetchall()
    changed_sources = [row['id'] for row in rows if row['id'] not in baseline or any(row[key] != baseline[row['id']][key] for key in ('document_id', 'content', 'page', 'chunk_index'))]
    repaired = sum(any(row['metadata'].get(key) != baseline[row['id']]['metadata'].get(key) for key in ('hs_heading', 'hs_chapter', 'hs_section')) for row in rows if row['id'] in baseline)
    real = [row for row in rows if 'DEMO DATA' not in row['title'].upper()]
    meaningful = [row for row in real if row['search_text']]
    current = [row for row in meaningful if row['embedded'] and row['metadata'].get('embedding_normalization_version') == NORMALIZATION_VERSION]
    report = {'chunks': len(rows), 'normalized': sum(row['search_text'] is not None for row in rows),
              'source_content_ids_pages_preserved': not changed_sources and set(baseline) == {row['id'] for row in rows},
              'repaired_context_vs_original': repaired,
              'real_documents': len({row['document_id'] for row in real}),
              'meaningful_real_chunks': len(meaningful), 'empty_page_markers_preserved': len(real) - len(meaningful),
              'current_embeddings': len(current), 'remaining_embeddings': len(meaningful) - len(current),
              'baseline_backup': str(baseline_path.relative_to(root))}
    (directory / 'integrity-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
    assert report['source_content_ids_pages_preserved'], 'Original source/citation integrity changed'
    assert report['normalized'] == report['chunks'], 'A chunk lacks its normalized representation'
