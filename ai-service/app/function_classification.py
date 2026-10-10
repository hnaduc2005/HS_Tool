"""One function gate used by retrieval, prompts, recovery and final validation."""
from . import electrical_classification as electrical
from . import textile_machinery as textile
from .legal_text import contains_phrase


def product_function(description: str) -> str | None:
    textile_function = textile.textile_function(description)
    return 'textile:' + textile_function if textile_function else electrical.electrical_function(description)


def function_candidates(description: str, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    if textile.textile_function(description):
        return textile.textile_candidates(description, candidates)
    return electrical.function_candidates(description, candidates)


def function_evidence_phrases(function: str) -> list[str]:
    return textile.textile_evidence_phrases(function.split(':')[1]) if function.startswith('textile:') else electrical.function_evidence_phrases(function)


def function_source_ids(function: str, chunks: list[dict]) -> list[str]:
    if function.startswith('textile:'):
        return textile.textile_source_ids(function.split(':')[1], chunks)
    return electrical.function_source_ids(function, chunks)


def function_recovery_queries(function: str) -> list[str]:
    if function.startswith('textile:'):
        return ['máy dệt kim', 'máy khâu đính', 'máy tạo búi']
    return [{'static_converter': 'máy biến đổi tĩnh điện', 'transformer': 'máy biến điện', 'inductor': 'cuộn cảm', 'ballast': 'chấn lưu'}[function]]
