"""Restore uncoded hierarchy labels from the supplied catalog workbook.

Dry run by default. --apply updates only imported rows with a semantic change
and writes their previous descriptions to artifacts for a reversible refresh.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app.config import database_url
from app.document_parser import parse_hs

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
source = ROOT / 'HS_AI' / 'TL' / 'BIEU THUE XNK 2026.xlsx'
catalog = {row['code']: row['description'] for row in parse_hs(source)}
provenance = f'Imported from {source.name}'
with psycopg.connect(database_url()) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT code, description FROM hs_codes WHERE provenance=%s', (provenance,))
        changes = [{'code': code, 'previous_description': description, 'description': catalog[code]}
                   for code, description in cursor.fetchall() if code in catalog
                   and re.sub(r'^[\s-]+', '', description).strip() != catalog[code]]
        if args.apply and changes:
            backup = ROOT / 'artifacts' / f'catalog-descriptions-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json'
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding='utf-8')
            cursor.executemany('UPDATE hs_codes SET description=%s WHERE code=%s AND provenance=%s',
                               [(row['description'], row['code'], provenance) for row in changes])
            print(json.dumps({'updated': len(changes), 'backup': str(backup)}))
        else:
            print(json.dumps({'semantic_changes': len(changes), 'applied': False,
                              'examples': changes[:3] + [row for row in changes if row['code'] in ('16024911', '16024991')]}))
