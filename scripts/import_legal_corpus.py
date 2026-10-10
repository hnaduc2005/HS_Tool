"""Import the supplied HS reference for heading/chapter and keyword retrieval."""
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4
import psycopg

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ai-service'))
from app.config import database_url, storage_root
from app.document_parser import chunks

source = root / 'HS_AI' / 'TL' / 'Chu giai HS 2022 Toan tap (HQKV8).pdf'
parts = list(chunks(source))
title = 'Chú giải HS 2022 toàn tập — tài liệu người dùng cung cấp'
with psycopg.connect(database_url()) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM documents WHERE title=%s', (title,))
        existing = cursor.fetchone()
        if existing:
            print(json.dumps({'already_imported': str(existing[0])}))
            sys.exit(0)
        document_id = str(uuid4())
        target = storage_root() / f'{document_id}.pdf'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        cursor.execute('INSERT INTO documents(id,title,document_type,source,version,file_url,status) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       (document_id, title, 'PDF', 'Tệp Chu giai HS 2022 Toan tap (HQKV8).pdf do người dùng cung cấp; cần kiểm chứng nguồn và hiệu lực.', 'HS 2022', str(target), 'READY'))
        rows = [(str(uuid4()), document_id, content, page, index,
                 json.dumps({**metadata, 'retrieval_mode': 'heading_keyword'}, ensure_ascii=False))
                for index, (content, page, metadata) in enumerate(parts)]
        cursor.executemany('INSERT INTO document_chunks(id,document_id,content,page,chunk_index,metadata) VALUES (%s,%s,%s,%s,%s,%s::jsonb)', rows)
print(json.dumps({'document_id': document_id, 'chunks': len(parts),
                  'headings': len({m.get('hs_heading') for _, _, m in parts if m.get('hs_heading')})}), flush=True)
