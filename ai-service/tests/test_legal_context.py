from pathlib import Path
from app import document_parser


def test_heading_with_trailing_dot_is_not_assigned_to_previous_heading(monkeypatch):
    def extract(path):
        yield '84.80 - Khuôn.\n84.81. - Vòi, van.\n8481.20 - Van khí nén.', 1951, {}
        yield 'Các van dùng trong hệ truyền động.', 1952, {}
    monkeypatch.setattr(document_parser, 'extract', extract)
    parts = list(document_parser.chunks(Path('legal.pdf')))
    assert next(m for c, p, m in parts if 'Vòi, van' in c)['hs_heading'] == '8481'
    assert next(m for c, p, m in parts if p == 1952)['hs_heading'] == '8481'


def test_legal_context_carries_chapter_and_heading_across_pages(monkeypatch):
    def extract(path):
        yield 'Phần IV\nChương 16\nChú giải 2. Chế phẩm thực phẩm trên 20%.', 1, {}
        yield 'Tiếp theo chú giải chương.\n16.05 - Động vật giáp xác đã chế biến.\n1605.29 - Loại khác.', 2, {}
        yield 'Phần giải thích của nhóm tiếp theo. (Chương 3) là dẫn chiếu.', 3, {}
        yield 'Chương 19\nChú giải loại trừ.', 4, {}
    monkeypatch.setattr(document_parser, 'extract', extract)
    parts = list(document_parser.chunks(Path('legal.pdf')))
    chapter_note = next(m for c, p, m in parts if 'Chú giải 2.' in c)
    assert chapter_note['hs_chapter'] == '16'
    assert chapter_note['legal_kind'] == 'chapter_note'
    continued_heading = next(m for c, p, m in parts if p == 3)
    assert continued_heading['hs_heading'] == '1605'
    assert continued_heading['hs_section'] == 'IV'
    next_chapter = next(m for c, p, m in parts if p == 4)
    assert next_chapter['hs_chapter'] == '19'
    assert next_chapter['hs_heading'] is None
