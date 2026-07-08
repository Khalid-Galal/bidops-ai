"""Tests for context_builder prompt hardening.

Covers finding 14c (enumerate valid filenames + copy-filename-exactly rule) and
finding 16 (submission-precedence rule replaces the hard skip-other-categories
rule) in the checklist prompt.
"""

from __future__ import annotations

from app.services.extraction.checklist_definitions import CHECKLIST_CATEGORIES
from app.services.extraction.field_definitions import SUMMARY_FIELDS
from app.services.llm.context_builder import (
    _valid_documents_block,
    build_checklist_extraction_prompt,
    build_extraction_prompt,
    build_labeled_context,
)
from app.services.search.hybrid_search import SearchResult


def _chunk(filename: str, chunk_id: str = "c1", page: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        text="body text",
        score=0.5,
        document_id=1,
        page_number=page,
        language="en",
        filename=filename,
        chunk_type="text",
        section_name=None,
    )


def _context(*filenames: str) -> str:
    chunks = [_chunk(f, chunk_id=f"c{i}", page=i + 1) for i, f in enumerate(filenames)]
    return build_labeled_context(chunks)


def test_valid_documents_block_enumerates_unique_filenames() -> None:
    ctx = _context("Tender A.pdf", "Tender A.pdf", "Annex B.docx")
    block = _valid_documents_block(ctx)
    assert "VALID DOCUMENTS" in block
    assert "- Tender A.pdf" in block
    assert "- Annex B.docx" in block
    # Deduplicated -- only one bullet per filename.
    assert block.count("- Tender A.pdf") == 1


def test_valid_documents_block_empty_when_no_labels() -> None:
    assert _valid_documents_block("no labels here") == ""


def test_field_prompt_has_exact_filename_rule_and_valid_documents() -> None:
    ctx = _context("Tender A.pdf")
    prompt = build_extraction_prompt(SUMMARY_FIELDS[0], ctx)
    assert "copy the filename EXACTLY" in prompt
    assert "VALID DOCUMENTS" in prompt
    assert "- Tender A.pdf" in prompt


def test_enum_field_prompt_maps_to_valid_value_token() -> None:
    contract_type_field = next(f for f in SUMMARY_FIELDS if f.name == "contract_type")
    ctx = _context("Tender A.pdf")
    prompt = build_extraction_prompt(contract_type_field, ctx)
    assert "VALID VALUES" in prompt
    assert "Map the value found in the document to the closest matching token" in prompt
    assert "return that exact snake_case token" in prompt
    # Citation quote must still preserve verbatim source wording.
    assert "do NOT substitute the VALID VALUES token here" in prompt


def test_non_enum_field_prompt_keeps_exact_copy_rule() -> None:
    ctx = _context("Tender A.pdf")
    prompt = build_extraction_prompt(SUMMARY_FIELDS[0], ctx)
    assert "Copy the EXACT value as it appears in the source document." in prompt


def test_checklist_prompt_uses_precedence_rule_not_skip_rule() -> None:
    ctx = _context("Tender A.pdf")
    prompt = build_checklist_extraction_prompt(CHECKLIST_CATEGORIES[0], ctx)
    # New submission-precedence rule present...
    assert "must be SUBMITTED" in prompt
    assert "Submission Documents" in prompt
    # ...and the old hard skip-other-categories rule is gone.
    assert "belong to other categories" not in prompt


def test_checklist_prompt_has_exact_filename_rule_and_valid_documents() -> None:
    ctx = _context("Tender A.pdf")
    prompt = build_checklist_extraction_prompt(CHECKLIST_CATEGORIES[0], ctx)
    assert "copy the filename EXACTLY" in prompt
    assert "VALID DOCUMENTS" in prompt
    assert "- Tender A.pdf" in prompt
