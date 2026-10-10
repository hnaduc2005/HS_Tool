"""Search extracted PDF text without treating line wrapping as word boundaries."""
import re
from .document_normalization import searchable_text


def normalized_legal_text(text: str) -> str:
    return searchable_text(text).casefold()


def contains_phrase(text: str, phrase: str) -> bool:
    return normalized_legal_text(phrase) in normalized_legal_text(text)


def phrase_search_pattern(phrase: str) -> str:
    # Match wrapping whitespace, not arbitrary intervening sentences.
    return r'[[:space:]]+'.join(re.escape(word) for word in phrase.split())
