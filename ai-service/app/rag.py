import json
import os
import re
import unicodedata
import httpx
import logging
from difflib import SequenceMatcher
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from .ai_client import AIProvider, motor_power_options
from .document_parser import chunks
from .embeddings import embed_batches
from .config import database_url
from .food_composition import review_food_composition
from .catalog_conditions import catalog_branch, valve_scenarios, matching_valve_hypothesis
from .electrical_classification import converter_scenarios
from .function_classification import product_function, function_candidates, function_evidence_phrases, function_source_ids, function_recovery_queries
from .textile_machinery import textile_scenarios, matching_textile_hypothesis, matching_textile_completed, missing_primary_branch
from .legal_text import phrase_search_pattern
from .document_normalization import normalized_chunk, embedding_text, NORMALIZATION_VERSION
from .product_understanding import identity_review_errors
from .coated_paper import paper_profile, paper_comparisons

def vector_literal(vector: list[float]) -> str:
    return '[' + ','.join(str(float(value)) for value in vector) + ']'

def terms(text: str) -> set[str]:
    plain = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    return {word for word in re.findall(r'[a-z0-9]+', plain) if len(word) > 2}

def lexical(a: str, b: str) -> float:
    ta, tb = terms(a), terms(b)
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    return max(jaccard, SequenceMatcher(None, a.lower()[:200], b.lower()[:200]).ratio() * 0.55)


def mentions_code(content: str, code: str) -> bool:
    groups = [code[:4]] + [code[index:index + 2] for index in range(4, len(code), 2)]
    return bool(re.search(r'(?<!\d)' + r'[.\s]*'.join(groups) + r'(?!\d)', content))


def clean_code(value: object) -> str:
    """Accept dotted HS formatting without accepting a new candidate code."""
    return re.sub(r'\D', '', value) if isinstance(value, str) else ''


def catalog_recovery_hints(answer: dict, allowed_codes: set[str]) -> dict:
    raw = answer.get('catalog_hints') if isinstance(answer.get('catalog_hints'), dict) else {}
    hints = raw.get('heading_hints') if isinstance(raw.get('heading_hints'), list) else []
    analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    hypotheses = analysis.get('hypotheses') if isinstance(analysis.get('hypotheses'), list) else []
    codes = [clean_code(answer.get('recommended_code'))] + [clean_code(item.get('code')) for item in hypotheses if isinstance(item, dict)]
    codes.extend(clean_code(article.get('code')) for item in hypotheses if isinstance(item, dict)
                 for article in (item.get('items') if isinstance(item.get('items'), list) else []) if isinstance(article, dict))
    missing_codes = [code for code in codes if len(code) in (4, 6, 8) and code not in allowed_codes]
    prefixes = list(dict.fromkeys(clean_code(item) for item in codes + hints
                                 if len(clean_code(item)) in (4, 6, 8)))[:4] if missing_codes or hints else []
    queries = list(dict.fromkeys(item.strip()[:100] for item in raw.get('queries', [])
                               if isinstance(item, str) and len(item.strip()) >= 3))[:6] if isinstance(raw.get('queries'), list) else []
    return {'heading_hints': prefixes, 'queries': queries}

def normalize(description: str) -> dict:
    text = description.lower()
    quoted_name = re.search(r'«([^»]+)»', description)
    normalized = {
        'product_name': quoted_name.group(1).strip() if quoted_name else description.splitlines()[0].split(',')[0].strip(),
        'material': 'gỗ' if re.search(r'\bwood(?:en)?\b|(?<!\w)gỗ(?!\w)', text) else next((word for word in ['cotton', 'da', 'thép', 'nhựa'] if re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text)), None),
        'construction': 'knitted' if any(word in text for word in ['dệt kim', 'áo thun', 'áo phông']) else ('woven' if 'dệt thoi' in text else None),
        'gender': 'male' if re.search(r'(?<!\w)nam(?!\w)', text) else ('female' if re.search(r'(?<!\w)nữ(?!\w)', text) else None),
        'usage': next((word for word in ['mặc', 'lọc nước', 'bơm nước', 'chiếu sáng'] if word in text), None),
    }
    profile = paper_profile(description)
    if profile:
        normalized.update({'material': 'giấy', 'coating': profile['coating'], 'width': profile['width'],
            'grammage_declared': profile['grammage_quote'] or profile['shorthand_quote']})
    return normalized


def preliminary_review(description: str, candidates: list[dict]) -> tuple[dict, list[str], dict]:
    normalized = normalize(description)
    composition, notes = review_food_composition(description)
    normalized.update(composition)
    return normalized, notes, composition


def preliminary_result(description: str, candidates: list[dict]) -> dict | None:
    normalized, notes, _ = preliminary_review(description, candidates)
    if not notes:
        return None
    return {
        'status': 'INSUFFICIENT_EVIDENCE',
        'normalized_product': normalized,
        'missing_information': notes + ['Cần đối chiếu đầy đủ tài liệu và xác nhận thành phần trước khi chốt mã.'],
        'candidates': [],
        'sources': [],
        'legal_analysis': {
            'summary': 'Đã kiểm tra sơ bộ dữ kiện nhưng chưa thể xác nhận căn cứ pháp lý từ kho tài liệu trong lượt tra cứu này.',
            'product_facts': [description[:1000]], 'legal_steps': [], 'alternatives': [],
            'conclusion': f'Mã {normalized["provisional_code"]} chỉ là hướng đối chiếu có điều kiện.' if normalized.get('provisional_code') else 'Chưa thể kết luận mã HS.',
            'limitations': notes + ['Dịch vụ phân tích hoặc nguồn pháp lý chưa sẵn sàng; cần kiểm tra trực tiếp văn bản trước khi sử dụng mã.'],
        },
    }


def unavailable_result(description: str, candidates: list[dict]) -> dict:
    preliminary = preliminary_result(description, candidates)
    if preliminary: return preliminary
    missing = ['Dịch vụ phân tích tạm thời không sẵn sàng; cần thử lại để đối chiếu điều khoản và mã HS.']
    return {'status': 'INSUFFICIENT_EVIDENCE', 'normalized_product': normalize(description),
            'missing_information': missing, 'candidates': [], 'sources': [],
            'legal_analysis': {'summary': 'Chưa thể xác minh căn cứ pháp lý trong lượt tra cứu này.',
                               'product_facts': [description[:1000]], 'legal_steps': [], 'alternatives': [],
                               'conclusion': 'Chưa xác định mã HS.', 'limitations': missing}}


def legal_analysis(answer: dict, description: str, chunks_found: list[dict], allowed_codes: set[str], missing: list[str], comparison_codes: set[str] | None = None) -> dict:
    """Keep only legal claims tied to retrieved source IDs; never trust model metadata."""
    raw = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
    source_map = {row['id']: row for row in chunks_found}
    def cited(value) -> list[str]:
        return list(dict.fromkeys(item for item in (value if isinstance(value, list) else []) if isinstance(item, str) and item in source_map))[:5]
    steps = []
    for item in raw.get('legal_steps', []) if isinstance(raw.get('legal_steps'), list) else []:
        if not isinstance(item, dict): continue
        ids = cited(item.get('source_chunk_ids'))
        rule, application = str(item.get('rule') or '').strip(), str(item.get('application') or '').strip()
        if ids and rule and application:
            steps.append({'rule': rule[:1500], 'application': application[:2000], 'source_chunk_ids': ids})
    alternatives = []
    for item in raw.get('alternatives', []) if isinstance(raw.get('alternatives'), list) else []:
        if not isinstance(item, dict) or clean_code(item.get('code')) not in (comparison_codes if comparison_codes is not None else allowed_codes): continue
        reason = str(item.get('reason') or '').strip()
        ids = cited(item.get('source_chunk_ids'))
        if reason and ids:
            alternatives.append({'code': clean_code(item['code']), 'reason': reason[:1200], 'source_chunk_ids': ids})
    hypotheses = []
    for item in raw.get('hypotheses', []) if isinstance(raw.get('hypotheses'), list) else []:
        if not isinstance(item, dict): continue
        code = clean_code(item.get('code'))
        assumptions = list(dict.fromkeys(value.strip()[:500] for value in item.get('assumptions', [])
                                        if isinstance(value, str) and value.strip())) if isinstance(item.get('assumptions'), list) else []
        ids, reason = cited(item.get('source_chunk_ids')), str(item.get('reasoning') or '').strip()
        mode = 'separate' if item.get('classification_mode') == 'separate' else 'single'
        articles = []
        if mode == 'separate':
            raw_articles = item.get('items') if isinstance(item.get('items'), list) else []
            for article in raw_articles[:6]:
                if not isinstance(article, dict): continue
                article_code = clean_code(article.get('code'))
                name, article_ids = str(article.get('name') or '').strip(), cited(article.get('source_chunk_ids'))
                if len(article_code) == 8 and article_code in allowed_codes and name and article_ids:
                    articles.append({'name': name[:150], 'code': article_code, 'source_chunk_ids': article_ids})
            if len(articles) < 2 or len(articles) != len(raw_articles) or code != articles[0]['code']:
                continue
            ids = list(dict.fromkeys(ids + [source for article in articles for source in article['source_chunk_ids']]))
        if len(code) == 8 and code in allowed_codes and assumptions and ids and reason:
            hypotheses.append({'code': code, 'label': str(item.get('label') or 'Giả định phân loại')[:200],
                               'classification_mode': mode, 'items': articles,
                               'assumed_attributes': [a for a in item.get('assumed_attributes', []) if isinstance(a, dict) and isinstance(a.get('attribute'), str) and isinstance(a.get('value'), str)][:12] if isinstance(item.get('assumed_attributes'), list) else [],
                               'assumptions': assumptions[:6], 'reasoning': reason[:1800], 'source_chunk_ids': ids})
    decisions = []
    for item in raw.get('decision_questions', []) if isinstance(raw.get('decision_questions'), list) else []:
        if not isinstance(item, dict): continue
        question, answer = str(item.get('question') or '').strip(), str(item.get('answer') or '').strip()
        if question and answer:
            decisions.append({'question': question[:200], 'answer': answer[:900], 'source_chunk_ids': cited(item.get('source_chunk_ids'))})
    facts = [str(item)[:500] for item in raw.get('product_facts', []) if isinstance(item, str)] if isinstance(raw.get('product_facts'), list) else []
    limits = [str(item)[:500] for item in raw.get('limitations', []) if isinstance(item, str)] if isinstance(raw.get('limitations'), list) else []
    return {
        'summary': str(raw.get('summary') or answer.get('reasoning') or 'Kết quả phân tích theo dữ kiện được cung cấp.')[:1500],
        'product_facts': facts[:12] or [description[:1000]],
        'decision_questions': decisions[:8],
        'legal_steps': steps[:10], 'alternatives': alternatives[:6], 'hypotheses': hypotheses[:6],
        'conclusion': str(raw.get('conclusion') or 'Chưa đủ căn cứ để kết luận mã HS.')[:1500],
        'limitations': list(dict.fromkeys(limits + missing))[:12],
        'suggested_name': str(raw.get('suggested_name') or '')[:700],
        'declaration_details': [str(item)[:300] for item in raw.get('declaration_details', []) if isinstance(item, str)][:8]
            if isinstance(raw.get('declaration_details'), list) else [],
    }


def cited_sources(chunks_found: list[dict], ids: set[str]) -> list[dict]:
    return [{'chunk_id': row['id'], 'document_id': row['document_id'], 'page': row['page'],
             'relevance_score': round(row['rerank_score'], 3)} for row in chunks_found if row['id'] in ids][:12]

async def index_document(document_id: str, path, provider: AIProvider) -> int:
    parts = list(chunks(path))
    if not parts: raise ValueError('Document contains no extractable text')
    context, prepared = {}, []
    for content, page, metadata in parts:
        text, metadata, context = normalized_chunk(content, metadata, context)
        if text:
            prepared.append((content, page, metadata, text))
    if not prepared: raise ValueError('Document contains no searchable text')
    vectors = await embed_batches(provider, [embedding_text(content, metadata) for content, _, metadata, _ in prepared])
    dsn = database_url()
    async with await psycopg.AsyncConnection.connect(dsn) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute('DELETE FROM document_chunks WHERE document_id = %s', (document_id,))
            for index, ((content, page, metadata, text), vector) in enumerate(zip(prepared, vectors)):
                metadata = {**metadata, 'embedding_normalization_version': NORMALIZATION_VERSION}
                await cursor.execute('INSERT INTO document_chunks(id, document_id, content, page, chunk_index, embedding, metadata, search_text) VALUES (%s,%s,%s,%s,%s,%s::vector,%s::jsonb,%s)',
                    (str(uuid4()), document_id, content, page, index, vector_literal(vector), json.dumps(metadata, ensure_ascii=False), text))
    return len(prepared)

async def retrieve(description: str, provider: AIProvider, candidates: list[dict] | None = None) -> list[dict]:
    dsn = database_url()
    headings = list(dict.fromkeys(c['code'][:4] for c in sorted(candidates or [], key=lambda c: float(c.get('score') or 0), reverse=True)))[:6]
    chapters = list(dict.fromkeys(code[:2] for code in headings))
    multi_article = bool(re.search(r'bộ\s+(?:quà|hàng|sản phẩm)|quà tặng|\bgift\b|\bset\b', description.lower()))
    guided = []
    general = []
    async with await psycopg.AsyncConnection.connect(dsn, row_factory=dict_row) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT count(*) AS total FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='READY' AND d.title NOT ILIKE '%DEMO DATA%' AND d.source NOT ILIKE '%minh họa%'")
            if (await cursor.fetchone())['total'] == 0: return []
            semantic = []
            try:
                vector = vector_literal((await provider.embed([description], task_type='RETRIEVAL_QUERY'))[0])
            except (httpx.RequestError, httpx.HTTPStatusError) as error:
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in (429, 500, 502, 503, 504):
                    raise
                vector = None
                logging.getLogger('hs-ai').warning('Semantic query unavailable; continuing normalized keyword and legal context retrieval')
            if vector is not None:
                await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                    GREATEST(0, 1 - (c.embedding <=> %s::vector)) AS semantic_score,
                    similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                    FROM document_chunks c JOIN documents d ON d.id=c.document_id
                    WHERE d.status='READY' AND d.title NOT ILIKE '%%DEMO DATA%%' AND d.source NOT ILIKE '%%minh họa%%' AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> %s::vector LIMIT 20''', (vector, description, vector))
                semantic = await cursor.fetchall()
            await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                FROM document_chunks c JOIN documents d ON d.id=c.document_id
                WHERE d.status='READY' AND d.title NOT ILIKE '%%DEMO DATA%%' AND d.source NOT ILIKE '%%minh họa%%' AND (COALESCE(c.search_text,c.content) %% %s OR COALESCE(c.search_text,c.content) ILIKE '%%' || %s || '%%')
                ORDER BY keyword_score DESC LIMIT 20''', (description, description, description))
            keyword = await cursor.fetchall()
            if paper_profile(description):
                for topic, heading, pattern in [('plastic_subheading', '4811', r'4811[.]5[19]'),
                        ('surface_decoration', '4811', r'tạo[[:space:]]+vân[[:space:]]+bề[[:space:]]+mặt|in[[:space:]]+mẫu[[:space:]]+hình'),
                        ('coating_thickness', '4811', r'một[[:space:]]+nửa[[:space:]]+tổng[[:space:]]+độ[[:space:]]+dày'),
                        ('polyurethane_definition', '3909', r'polyurethan|polyuretan')]:
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND c.metadata->>'hs_heading'=%s AND COALESCE(c.search_text,c.content) ~* %s
                        ORDER BY c.page, c.chunk_index LIMIT 1''', (description, heading, pattern))
                    for row in await cursor.fetchall():
                        row['metadata'] = {**(row.get('metadata') or {}), 'retrieval_topic': 'coated_paper:' + topic}
                        guided.append(row)
            function = product_function(description)
            if function:
                eligible, _ = function_candidates(description, candidates or [])
                function_headings = list(dict.fromkeys(c['code'][:4] for c in eligible))[:2]
                for heading in function_headings:
                    # Reserve each mechanism's definition, including alternatives.
                    # One shared LIMIT can discard a later subsection such as
                    # crochet trimming machines while keeping only flat knitting.
                    for phrase in function_evidence_phrases(function):
                        await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND c.metadata->>'hs_heading'=%s AND COALESCE(c.search_text,c.content) ~* %s
                        ORDER BY c.page, c.chunk_index LIMIT 1''', (description, heading, phrase_search_pattern(phrase)))
                        for row in await cursor.fetchall():
                            row['metadata'] = {**(row.get('metadata') or {}), 'retrieval_topic': function + ':definition:' + phrase}
                            guided.append(row)
                for prefix in list(dict.fromkeys(c['code'][:6] for c in eligible))[:4]:
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND c.metadata->>'hs_heading'=%s AND COALESCE(c.search_text,c.content) ILIKE %s
                        ORDER BY c.page, c.chunk_index LIMIT 1''', (description, prefix[:4], '%' + prefix[:4] + '.' + prefix[4:] + '%'))
                    for row in await cursor.fetchall():
                        row['metadata'] = {**(row.get('metadata') or {}), 'retrieval_topic': function + ':' + prefix}
                        guided.append(row)
            if headings:
                # Reserve evidence for every constituent heading before the
                # broad note search; long section notes can otherwise fill its limit.
                for heading in headings:
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND c.metadata->>'hs_heading'=%s
                        AND c.metadata->>'legal_kind'='heading'
                        ORDER BY (COALESCE(c.search_text,c.content) ILIKE %s) DESC, keyword_score DESC, c.page, c.chunk_index LIMIT 2''',
                                         (description, heading, f'%{heading[:2]}.{heading[2:]}%'))
                    guided.extend(await cursor.fetchall())
                    # Older indexes may have missed punctuation in a heading title.
                    # Recover by the actual text, including subheading notes; don't
                    # trust inherited metadata as proof that the text is relevant.
                    pattern = rf'(^|\n)[[:space:]]*{heading[:2]}[.]{heading[2:]}[.]?[[:space:]]*[-–]|{heading}[.][0-9]{{2}}'
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND d.title NOT ILIKE '%%DEMO DATA%%' AND c.content ~ %s
                        ORDER BY (c.content ~ %s) DESC, keyword_score DESC, c.page, c.chunk_index LIMIT 3''',
                        (description, pattern, rf'(^|\n)[[:space:]]*{heading[:2]}[.]{heading[2:]}[.]?[[:space:]]*[-–]'))
                    for recovered in await cursor.fetchall():
                        recovered['metadata'] = {**(recovered.get('metadata') or {}), 'retrieval_heading': heading}
                        guided.append(recovered)
                await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                    c.metadata, 0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                    FROM document_chunks c JOIN documents d ON d.id=c.document_id
                    WHERE d.status='READY' AND (
                        c.metadata->>'hs_heading'=ANY(%s)
                        OR (c.metadata->>'legal_kind'='chapter_note' AND c.metadata->>'hs_chapter'=ANY(%s))
                        OR (c.metadata->>'legal_kind'='section_note' AND c.metadata->>'hs_section' IN (
                            SELECT DISTINCT metadata->>'hs_section' FROM document_chunks WHERE metadata->>'hs_chapter'=ANY(%s)
                        ))) ORDER BY keyword_score DESC LIMIT 80''', (description, headings, chapters, chapters))
                guided.extend(await cursor.fetchall())
            if multi_article:
                # Keep the rule text and retail-set criteria even when keyword
                # search ranks examples above the operative provisions.
                for phrase in ('refer to part only', 'last in numerical order', 'particular need or carry out a specific activity'):
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND d.title ILIKE '%%quy tắc%%' AND COALESCE(c.search_text,c.content) ILIKE %s
                        ORDER BY c.page, c.chunk_index LIMIT 2''', (description, f'%{phrase}%'))
                    general.extend(await cursor.fetchall())
                if {'61', '62'} & set(chapters):
                    await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                        0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                        FROM document_chunks c JOIN documents d ON d.id=c.document_id
                        WHERE d.status='READY' AND c.metadata->>'hs_chapter'=ANY(%s)
                        AND COALESCE(c.search_text,c.content) ILIKE '%%Chú giải 14%%' AND COALESCE(c.search_text,c.content) ILIKE '%%61.01%%'
                        ORDER BY c.page, c.chunk_index LIMIT 1''', (description, chapters))
                    general.extend(await cursor.fetchall())
            for rule in ('1', '6'):
                await cursor.execute('''SELECT c.id::text, c.document_id::text, c.content, c.page, d.title, d.source,
                    0.0 AS semantic_score, similarity(COALESCE(c.search_text,c.content), %s) AS keyword_score
                    FROM document_chunks c JOIN documents d ON d.id=c.document_id
                    WHERE d.status='READY' AND d.title ILIKE '%%quy tắc%%'
                    AND (COALESCE(c.search_text,c.content) ILIKE %s OR COALESCE(c.search_text,c.content) ILIKE %s)
                    ORDER BY c.page, c.chunk_index LIMIT 2''', (description, f'%QUI TẮC {rule}%', f'%QUY TẮC {rule}%'))
                general.extend(await cursor.fetchall())
    merged = {row['id']: row for row in semantic}
    for row in keyword:
        if row['id'] in merged: merged[row['id']]['keyword_score'] = max(merged[row['id']]['keyword_score'], row['keyword_score'])
        else: merged[row['id']] = row
    for row in merged.values():
        row['rerank_score'] = 0.6 * max(0, float(row['semantic_score'])) + 0.2 * max(0, float(row['keyword_score'])) + 0.2 * lexical(description, row['content'])
    selected = []
    groups: dict[str, int] = {}
    for row in guided:
        metadata = row.get('metadata') or {}
        group = metadata.get('retrieval_topic') or f"{metadata.get('legal_kind')}:{metadata.get('retrieval_heading') or metadata.get('hs_heading') or metadata.get('hs_chapter') or metadata.get('hs_section')}"
        if groups.get(group, 0) >= (3 if metadata.get('retrieval_heading') else 2): continue
        groups[group] = groups.get(group, 0) + 1
        row['rerank_score'] = round(0.35 + 0.4 * lexical(description, row['content']), 3)
        selected.append(row)
    selected.extend(sorted(merged.values(), key=lambda row: row['rerank_score'], reverse=True)[:8])
    for row in general:
        row['rerank_score'] = 0.3
        selected.append(row)
    combined = {}
    for row in general + selected:
        if row['id'] in combined:
            for field in ('semantic_score', 'keyword_score', 'rerank_score'):
                combined[row['id']][field] = max(float(combined[row['id']][field]), float(row[field]))
        else:
            combined[row['id']] = dict(row)
    return list(combined.values())[:32 if multi_article else 24]

async def classify(description: str, candidates: list[dict], provider: AIProvider) -> dict:
    normalized, legal_notes, composition = preliminary_review(description, candidates)
    chunks_found = await retrieve(description, provider, candidates)
    if not chunks_found:
        missing = legal_notes + ['Chưa có tài liệu pháp lý phù hợp trong kho tri thức để đối chiếu mã HS.']
        return {'status': 'INSUFFICIENT_EVIDENCE', 'normalized_product': normalized, 'missing_information': missing, 'candidates': [], 'sources': [],
                'legal_analysis': {'summary': 'Chưa thể phân loại vì thiếu nguồn pháp lý có thể kiểm chứng.', 'product_facts': [description[:1000]], 'legal_steps': [], 'alternatives': [], 'conclusion': 'Chưa xác định mã HS.', 'limitations': missing}}
    compatible_candidates, excluded_functions = function_candidates(description, candidates)
    context = [{'chunk_id': c['id'], 'document_id': c['document_id'], 'title': c['title'], 'source': c.get('source'), 'page': c['page'], 'content': c['content'][:2400]} for c in chunks_found]
    understanding = None
    if isinstance(provider, AIProvider):
        # Resolve meaning using source definitions BEFORE any product scenarios.
        understanding = await provider.understandProduct(description, compatible_candidates, context)
        identity_codes = set(understanding['identity_eligible_codes'])
        compatible_candidates = [c for c in compatible_candidates if c['code'] in identity_codes]
    ranked_all = sorted(compatible_candidates, key=lambda c: max(lexical(description, c['description']), float(c.get('score') or 0), max((0.3 if mentions_code(chunk['content'], c['code']) else 0) for chunk in chunks_found)), reverse=True)
    # Four- and six-digit rows are hierarchy labels in the Vietnamese catalog.
    # Let the model compare declarable eight-digit children when they exist.
    eight_digit = [candidate for candidate in ranked_all if len(candidate['code']) == 8]
    pool = eight_digit if eight_digit else ranked_all
    # Keep competing headings visible when missing facts can change the branch.
    # Filling only from the highest-scoring heading can hide all other hypotheses.
    groups = {}
    for candidate in pool:
        groups.setdefault(candidate['code'][:4], []).append(candidate)
    # Preserve material branches within headings as well as competing headings.
    branches_by_heading = []
    for group in list(groups.values())[:6]:
        branches = {}
        for candidate in group:
            branches.setdefault(catalog_branch(candidate), []).append(candidate)
        for branch in branches.values():
            branch.sort(key=lambda candidate: (
                any(marker in candidate['description'].lower() and marker not in description.lower() for marker in ('batik', 'giãn tĩnh mạch', 'áp lực')),
                bool('công suất' in candidate['description'].lower() and not re.search(r'(?:^|→)\s*(?:loại khác|động cơ khác)\s*$', candidate['description'], re.I)),
            ))
        branches_by_heading.append(list(branches.values()))
    ordered_branches = [branches[index] for index in range(max((len(branches) for branches in branches_by_heading), default=0))
                        for branches in branches_by_heading if index < len(branches)]
    ranked = [branch[0] for branch in ordered_branches]
    selected_codes = {candidate['code'] for candidate in ranked}
    ranked.extend(candidate for candidate in pool if candidate['code'] not in selected_codes)
    priority_codes = {option['code'] for option in motor_power_options(description, pool)}
    priority_codes.update(option['code'] for option in valve_scenarios(description, pool))
    priority_codes.update(option['code'] for option in converter_scenarios(description, pool))
    priority_codes.update(option['code'] for option in textile_scenarios(description, pool))
    if priority_codes:
        ranked = [candidate for candidate in ranked if candidate['code'] in priority_codes] + [candidate for candidate in ranked if candidate['code'] not in priority_codes]
    ranked = ranked[:24]
    answer = await provider.classifyProduct(description, ranked, context, understanding=understanding) if isinstance(provider, AIProvider) else await provider.classifyProduct(description, ranked, context)
    if answer.get('status') == 'COMPLETED':
        comparisons = paper_comparisons(description, candidates, context)
        if comparisons:
            answer.setdefault('legal_analysis', {})['alternatives'] = comparisons
    allowed = {c['code']: c for c in ranked}
    recovery_hints = catalog_recovery_hints(answer, set(allowed))
    if understanding and not ranked:
        recovery_hints = catalog_recovery_hints({'catalog_hints': understanding.get('catalog_hints', {})}, set())
    function = product_function(description)
    if function and (not any(len(c['code']) == 8 for c in compatible_candidates) or missing_primary_branch(description, compatible_candidates)):
        recovery_hints = {'queries': function_recovery_queries(function), 'heading_hints': []}
    code = clean_code(answer.get('recommended_code'))
    arithmetic_missing = [note for note in legal_notes if 'cần xác nhận' in note or 'vượt 100%' in note]
    missing = list(dict.fromkeys(arithmetic_missing + (answer.get('missing_information') or [])))
    if understanding:
        raw_analysis = answer.get('legal_analysis') if isinstance(answer.get('legal_analysis'), dict) else {}
        raw_hypotheses = raw_analysis.get('hypotheses') if isinstance(raw_analysis.get('hypotheses'), list) else []
        raw_analysis['hypotheses'] = [h for h in raw_hypotheses if isinstance(h, dict) and not identity_review_errors({'legal_analysis': {'hypotheses': [h]}}, understanding)]
    analysis = legal_analysis(answer, description, chunks_found, set(allowed), missing, {candidate['code'] for candidate in candidates})
    if understanding:
        analysis['product_understanding'] = understanding
        normalized['product_name'] = understanding['product_name']
    if function:
        functional_ids = set(function_source_ids(function, context))
        analysis['hypotheses'] = [h for h in analysis['hypotheses'] if functional_ids.intersection(h['source_chunk_ids'])]
        if not functional_ids:
            missing.append('Chưa truy xuất được đoạn chú giải đúng nhánh chức năng của sản phẩm.')
            code = ''
    textile_options = textile_scenarios(description, ranked)
    if function and function.startswith('textile:'):
        analysis['hypotheses'] = [h for h in analysis['hypotheses'] if matching_textile_hypothesis(h, textile_options, context)]
        if missing_primary_branch(description, ranked):
            analysis['hypotheses'] = []
        if not analysis['hypotheses'] and not matching_textile_completed(code, textile_options, context):
            code = ''
    valve_options = valve_scenarios(description, ranked)
    if valve_options:
        # Even a failed repair must not let the original, incompletely justified
        # manual-gate proposal reach persistence or the UI.
        valid_hypotheses = [h for h in analysis['hypotheses'] if matching_valve_hypothesis(h, valve_options, context)]
        rejected = len(valid_hypotheses) != len(analysis['hypotheses'])
        priorities = {option['code']: option['priority'] for option in valve_options}
        analysis['hypotheses'] = sorted(valid_hypotheses, key=lambda h: priorities[h['code']])
        if rejected:
            missing.append('Đã loại phương án van chưa thể hiện đủ điều kiện nhánh cha hoặc chưa dẫn đúng chú giải van.')
        # A completed code follows the same physical condition gate.
        if answer.get('status') == 'COMPLETED' and not analysis['hypotheses']:
            code = ''
    analysis_ids = {id for entry in analysis['legal_steps'] + analysis['hypotheses'] + analysis['alternatives'] for id in entry['source_chunk_ids']}
    if understanding:
        analysis_ids.update(understanding['definition_source_ids'])
    if analysis['hypotheses']:
        first = analysis['hypotheses'][0]
        if first['classification_mode'] == 'separate':
            normalized['provisional_codes'] = [item['code'] for item in first['items']]
        else:
            normalized['provisional_code'] = first['code']
    requested_ids = set(answer.get('source_chunk_ids') or [])
    cited = [c for c in chunks_found if c['id'] in requested_ids | analysis_ids]
    declared_total = composition.get('declared_composition_percent')
    unsafe_composition = declared_total is not None and (declared_total < 99.99 or declared_total > 100.01)
    incomplete = answer.get('status') != 'COMPLETED' or bool(analysis['hypotheses']) or len(code) != 8 or code not in allowed or not cited or not analysis['legal_steps'] or unsafe_composition or bool(understanding and understanding['missing_attributes'])
    if incomplete:
        if not analysis['legal_steps']: missing.append('Chưa xác minh được điều khoản pháp lý cụ thể có trích dẫn hợp lệ.')
        if answer.get('status') == 'COMPLETED' and len(code) != 8:
            missing.append('Mã đề xuất mới ở cấp nhóm hoặc phân nhóm; cần đối chiếu mã 8 số của Danh mục hàng hóa xuất nhập khẩu Việt Nam.')
        if code not in allowed and code: missing.append('Mã HS do mô hình đề xuất không thuộc danh mục mã ứng viên đã kiểm tra.')
        if not cited: missing.append('Không có nguồn trích dẫn hợp lệ cho kết luận.')
        analysis['limitations'] = list(dict.fromkeys(analysis['limitations'] + missing))
        if not analysis['legal_steps']:
            analysis['summary'] = 'Chưa có điều khoản pháp lý được trích dẫn hợp lệ để giải thích kết quả phân loại.'
            analysis['conclusion'] = 'Chưa thể xác định mã HS từ tài liệu hiện có.'
        if analysis['hypotheses']:
            first = analysis['hypotheses'][0]
            proposed = ', '.join(f'{item["name"]}: {item["code"]}' for item in first['items']) if first['classification_mode'] == 'separate' else f'mã {first["code"]}'
            analysis['conclusion'] = f'Đề xuất có điều kiện {proposed} theo giả định ưu tiên: ' + '; '.join(first['assumptions']) + '. Các phương án bên trên áp dụng theo từng giả định tương ứng.'
            if re.search(r'chưa (?:đủ|thể)|không đủ|kịch bản bắt buộc|required_scenarios', analysis['summary'], re.I):
                analysis['summary'] = f'Phân loại theo {len(analysis["hypotheses"])} giả định cụ thể; phương án ưu tiên là {proposed}.'
        elif unsafe_composition:
            analysis['conclusion'] = 'Tỷ lệ thành phần chưa đầy đủ hoặc không hợp lệ; cần đối chiếu các giả định và mã tám số được hỗ trợ bởi tài liệu.'
        elif answer.get('status') == 'COMPLETED': analysis['conclusion'] = 'Chưa đủ căn cứ để chốt mã HS; cần kiểm tra thêm nguồn và dữ kiện.'
        status = 'CONDITIONAL' if analysis['hypotheses'] and analysis['legal_steps'] else 'INSUFFICIENT_EVIDENCE'
        if status == 'CONDITIONAL': analysis['product_facts'] = [description[:1000]]
        return {'status': status, 'normalized_product': normalized, 'missing_information': missing or ([] if analysis['hypotheses'] else ['Cần bổ sung nguồn pháp lý hoặc nhánh danh mục để đối chiếu']), 'candidates': [], 'sources': cited_sources(chunks_found, analysis_ids), 'legal_analysis': analysis, 'catalog_hints': recovery_hints}
    def score(candidate: dict, llm: float) -> float:
        semantic = max(max(0, float(c['semantic_score']), float(c['rerank_score'])) for c in cited)
        keyword = max(lexical(candidate['description'], c['content']) for c in cited)
        hs_match = max(
            1.0 if mentions_code(c['content'], candidate['code']) else
            0.85 if len(candidate['code']) == 8 and mentions_code(c['content'], candidate['code'][:6]) else
            lexical(description, candidate['description']) for c in cited
        )
        evidence = min(1, len(cited) / 2)
        return round(min(1.0, (0.30 * semantic + 0.20 * keyword + 0.20 * hs_match + 0.30 * max(0, min(1, llm))) * (0.75 + 0.25 * evidence)), 3)
    primary_score = score(allowed[code], float(answer.get('llm_score') or 0))
    if primary_score < 0.5:
        missing.append('Độ phù hợp của chứng cứ dưới ngưỡng; cần thêm mô tả hoặc tài liệu.')
        analysis['limitations'] = list(dict.fromkeys(analysis['limitations'] + missing))
        analysis['conclusion'] = 'Chưa đủ căn cứ để chốt mã HS.'
        return {'status': 'INSUFFICIENT_EVIDENCE', 'normalized_product': normalized, 'missing_information': missing, 'candidates': [], 'sources': cited_sources(chunks_found, analysis_ids), 'legal_analysis': analysis}
    others = []
    for item in answer.get('alternatives') or []:
        alternative_code = clean_code(item.get('code'))
        if alternative_code in allowed and alternative_code != code:
            others.append({'code': alternative_code, 'score': score(allowed[alternative_code], float(item.get('score') or 0)), 'reasoning': str(item.get('reasoning') or '')[:1500]})
    return {
        'status': 'COMPLETED', 'normalized_product': normalized,
        'missing_information': legal_notes[-1:] if composition.get('declared_composition_percent', 100) < 99.99 else (answer.get('missing_information') or []),
        'recommended_code': code, 'reasoning': str(answer.get('reasoning') or '')[:3000],
        'llm_score': primary_score, 'candidates': others[:3],
        'sources': cited_sources(chunks_found, {c['id'] for c in cited}), 'legal_analysis': analysis,
    }
