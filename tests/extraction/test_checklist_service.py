"""Tests for ChecklistService dedup precedence and matcher consolidation.

Covers finding 16 (submission_documents / eligibility win cross-category dedup)
and finding 14 (both extraction paths go through CitationVerifier._find_source_chunk).
No LLM or embedding model is loaded; all heavy collaborators are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from app.schemas.checklist import CategoryExtractionResponse, RequirementItem, VerifiedRequirement
from app.schemas.extraction import Citation
from app.services.extraction.checklist_definitions import CHECKLIST_CATEGORIES
from app.services.extraction.checklist_service import ChecklistService
from app.services.search.hybrid_search import SearchResult


def _req(requirement: str, category: str, confidence: float) -> VerifiedRequirement:
    return VerifiedRequirement(
        requirement=requirement,
        description="",
        category=category,
        is_mandatory=True,
        citation=Citation(document_name="d.pdf", page_number=1, quote="q"),
        nli_score=0.5,
        confidence=confidence,
        confidence_level="low",
        requires_review=True,
    )


class _FakeEmbed:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts):  # noqa: ANN001 - mirrors sentence-transformers API
        return np.array([self._vectors[t] for t in texts], dtype=float)


def _service_with_embeddings(vectors: dict[str, list[float]]) -> ChecklistService:
    search = MagicMock()
    search._embedding_service._get_model.return_value = _FakeEmbed(vectors)
    return ChecklistService(search, MagicMock(), MagicMock())


def test_dedup_submission_documents_wins_over_higher_confidence_commercial() -> None:
    # Commercial copy scores higher, but the submission_documents copy must
    # survive so the dedicated bucket is never starved.
    service = _service_with_embeddings(
        {
            "Submit tender bond with the bid": [1.0, 0.0],
            "Provide tender bond": [1.0, 0.0],  # near-duplicate (identical vector)
            "Comply with ISO 9001": [0.0, 1.0],  # distinct
        }
    )
    commercial = _req("Provide tender bond", "commercial", confidence=0.9)
    submission = _req("Submit tender bond with the bid", "submission_documents", 0.5)
    technical = _req("Comply with ISO 9001", "technical", confidence=0.7)

    result = service._deduplicate([commercial, submission, technical])

    categories = {r.category for r in result}
    assert "submission_documents" in categories
    assert "commercial" not in categories
    assert "technical" in categories


def test_dedup_survivor_independent_of_input_order() -> None:
    service = _service_with_embeddings(
        {
            "Submit audited financials": [1.0, 0.0],
            "Attach audited financials": [1.0, 0.0],
        }
    )
    submission = _req("Submit audited financials", "submission_documents", 0.4)
    eligibility = _req("Attach audited financials", "eligibility", 0.9)

    # submission_documents (priority 2) beats eligibility (priority 1) either way.
    result = service._deduplicate([eligibility, submission])
    assert [r.category for r in result] == ["submission_documents"]


def test_dedup_same_priority_keeps_higher_confidence() -> None:
    service = _service_with_embeddings(
        {
            "Provide method statement": [1.0, 0.0],
            "Submit method statement": [1.0, 0.0],
        }
    )
    lo = _req("Provide method statement", "technical", confidence=0.4)
    hi = _req("Submit method statement", "hse", confidence=0.8)

    result = service._deduplicate([lo, hi])
    assert [r.requirement for r in result] == ["Submit method statement"]


async def test_extract_category_uses_shared_matcher() -> None:
    category = CHECKLIST_CATEGORIES[0]
    chunk = SearchResult(
        chunk_id="c1",
        text="The bond is required.",
        score=0.72,
        document_id=1,
        page_number=2,
        language="en",
        filename="Tender A.pdf",
        chunk_type="text",
        section_name=None,
    )

    search = MagicMock()
    search.search.return_value = [chunk]

    llm = MagicMock()
    llm.extract.return_value = CategoryExtractionResponse(
        items=[
            RequirementItem(
                requirement="Provide tender bond",
                is_mandatory=True,
                source_document="Tender A.pdf",
                page_number=2,
                quote="The bond is required.",
                confidence=0.8,
            )
        ]
    )

    verifier = MagicMock()
    verifier._find_source_chunk.return_value = chunk
    verifier.verify_citation.return_value = 1.0
    verifier.calculate_confidence.return_value = (0.9, "high", False)

    service = ChecklistService(search, llm, verifier)
    verified = await service._extract_category(1, category)

    # The consolidated matcher on CitationVerifier was used (not an inline copy).
    assert verifier._find_source_chunk.call_count == 1
    passed_citation, passed_chunks = verifier._find_source_chunk.call_args.args
    assert passed_citation.document_name == "Tender A.pdf"
    assert passed_chunks == [chunk]
    assert len(verified) == 1
    assert verified[0].confidence == 0.9
