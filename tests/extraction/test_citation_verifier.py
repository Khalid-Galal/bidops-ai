"""Tests for CitationVerifier matching and the verbatim short-circuit.

Covers findings 14 (three-layer citation matching) and 15 (verbatim-quote
short-circuit that skips the NLI model). No model is ever loaded here.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.schemas.extraction import Citation
from app.services.extraction.citation_verifier import (
    CitationVerifier,
    _filenames_match,
    _normalize_for_match,
)
from app.services.search.hybrid_search import SearchResult


def _chunk(
    text: str,
    filename: str = "doc.pdf",
    page: int = 1,
    chunk_id: str = "c1",
    score: float = 0.7,
) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        text=text,
        score=score,
        document_id=1,
        page_number=page,
        language="en",
        filename=filename,
        chunk_type="text",
        section_name=None,
    )


class _FakeModel:
    """Stand-in NLI model; records whether predict() was invoked."""

    def __init__(self, logits: list[float]) -> None:
        self._logits = logits
        self.called = False

    def predict(self, pairs):  # noqa: ANN001 - mirrors CrossEncoder API
        self.called = True
        return np.array([self._logits])


# --------------------------------------------------------------------------
# Normalization helpers
# --------------------------------------------------------------------------

def test_normalize_collapses_case_and_whitespace() -> None:
    assert _normalize_for_match("Hello   World") == _normalize_for_match("hello world")


def test_normalize_strips_arabic_diacritics_and_tatweel() -> None:
    with_marks = "الشَّركـة"  # decorated
    without = "الشركة"
    assert _normalize_for_match(with_marks) == _normalize_for_match(without)


def test_filenames_match_case_unicode_and_extension() -> None:
    assert _filenames_match("Report.PDF", "report")
    assert _filenames_match("Tender Doc.docx", "tender doc.DOCX")
    assert not _filenames_match("a.pdf", "b.pdf")


# --------------------------------------------------------------------------
# _find_source_chunk: three-layer matching
# --------------------------------------------------------------------------

def test_find_source_chunk_matches_by_quote_despite_filename_drift() -> None:
    verifier = CitationVerifier()
    chunk = _chunk("Clause 5: The bond is required by law.", filename="Original Report.pdf")
    # LLM echoed a completely wrong filename, but the quote is verbatim.
    citation = Citation(
        document_name="wrong-name.pdf",
        page_number=99,
        quote="the bond is required",
    )
    assert verifier._find_source_chunk(citation, [chunk]) is chunk


def test_find_source_chunk_matches_arabic_quote_with_diacritics() -> None:
    verifier = CitationVerifier()
    source = "الشَّركة   تقدّم العطاء"
    quote = "الشركة تقدم"
    chunk = _chunk(source, filename="مستند.pdf")
    citation = Citation(document_name="other.pdf", page_number=1, quote=quote)
    assert verifier._find_source_chunk(citation, [chunk]) is chunk


def test_find_source_chunk_filename_fallback_when_quote_absent() -> None:
    verifier = CitationVerifier()
    chunk = _chunk("Some unrelated body text.", filename="report.pdf", page=3)
    # Quote is not present anywhere; fall back on filename (upper, no extension).
    citation = Citation(document_name="REPORT", page_number=3, quote="not in any chunk")
    assert verifier._find_source_chunk(citation, [chunk]) is chunk


def test_find_source_chunk_returns_none_without_any_match() -> None:
    verifier = CitationVerifier()
    chunk = _chunk("Body text.", filename="a.pdf")
    citation = Citation(document_name="b.pdf", page_number=1, quote="absent quote")
    assert verifier._find_source_chunk(citation, [chunk]) is None


# --------------------------------------------------------------------------
# verify_citation: verbatim short-circuit vs NLI fallback
# --------------------------------------------------------------------------

def test_verify_citation_verbatim_shortcircuits_without_model() -> None:
    verifier = CitationVerifier()

    def boom() -> object:
        raise AssertionError("NLI model must not load for a verbatim quote")

    verifier._get_model = boom  # type: ignore[assignment]

    score = verifier.verify_citation(
        claim="The Bond   is Required",
        source_text="Clause 5: the bond is required by law.",
    )
    assert score == 1.0


def test_verify_citation_non_verbatim_falls_back_to_nli() -> None:
    verifier = CitationVerifier()
    # logits [contradiction, entailment, neutral] -> entailment dominates.
    fake = _FakeModel([0.1, 3.0, 0.2])
    verifier._model = fake  # populate cache so _get_model returns it

    score = verifier.verify_citation(
        claim="completely different assertion",
        source_text="unrelated body text about weather",
    )
    assert fake.called is True
    assert score > 0.5
