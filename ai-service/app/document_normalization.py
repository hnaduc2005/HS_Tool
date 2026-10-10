"""A searchable representation alongside unchanged, traceable source text."""
import hashlib
import re
import unicodedata

NORMALIZATION_VERSION = 1
CONTEXT_MARKER = re.compile(r'(?mi)^[ \t]*(?:Phần[ \t]+(?P<section>[IVX]+)\b|Chương[ \t]+(?P<chapter>\d{1,2})\b|(?P<heading>\d{2}[.]\d{2})[.]?[ \t]*[-–—])')


def searchable_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    text = text.replace('\u00ad', '').replace('\u200b', '').replace('\ufeff', '').replace('\xa0', ' ')
    text = re.sub(r'(?m)^\s*[—–-]\s*\d{1,4}\s*[—–-]\s*$', '', text)
    text = ''.join(c for c in text if c.isspace() or unicodedata.category(c)[0] != 'C')
    return re.sub(r'\s+', ' ', text).strip()


def normalized_chunk(content: str, metadata: dict, context: dict) -> tuple[str, dict, dict]:
    """Repair inherited context from actual structural markers, not code mentions."""
    context = dict(context)
    for marker in CONTEXT_MARKER.finditer(content):
        if marker.group('section'):
            context = {'hs_section': marker['section'].upper(), 'legal_kind': 'section_note'}
        elif marker.group('chapter'):
            context = {k: v for k, v in context.items() if k == 'hs_section'}
            context.update({'hs_chapter': marker['chapter'].zfill(2), 'hs_heading': None, 'legal_kind': 'chapter_note'})
        else:
            heading = marker['heading'].replace('.', '')
            context = {k: v for k, v in context.items() if k == 'hs_section'}
            context.update({'hs_heading': heading, 'hs_chapter': heading[:2], 'legal_kind': 'heading'})
    result = {**metadata, **context}
    if context:
        result.pop('legal_subsection', None)
        result.pop('subsection_title', None)
    for marker in re.finditer(r'(?m)^\s*\(([A-Z]+)\)\s+([^\n]+)', content):
        context['legal_subsection'] = marker[1]
        context['subsection_title'] = searchable_text(marker[2])
    result.update({k: v for k, v in context.items() if k in ('legal_subsection', 'subsection_title')})
    rule = re.search(r'(?mi)^\s*(?:QUI TẮC|QUY TẮC|RULE)\s+([1-6])\b', content)
    if rule:
        context.update({'general_rule': rule[1], 'legal_kind': 'general_rule'})
        result.update(context)
    text = searchable_text(content)
    result.update({'normalization_version': NORMALIZATION_VERSION, 'source_content_hash': hashlib.sha256(content.encode('utf-8')).hexdigest()})
    return text, result, context


def embedding_text(content: str, metadata: dict) -> str:
    labels = [('Phần', 'hs_section'), ('Chương', 'hs_chapter'), ('Nhóm', 'hs_heading'), ('Mục', 'legal_subsection')]
    heading = '; '.join(label + ' ' + str(metadata[key]) for label, key in labels if metadata.get(key))
    title = metadata.get('subsection_title', '')
    return '\n'.join(part for part in (heading, title, searchable_text(content)) if part)
