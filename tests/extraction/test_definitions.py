"""Field/category definition coverage: spec-listed summary fields, new
checklist categories, and bilingual (Arabic) retrieval + prompt terms."""

from __future__ import annotations

from app.services.extraction.checklist_definitions import CHECKLIST_CATEGORIES
from app.services.extraction.field_definitions import SUMMARY_FIELDS
from app.services.llm.context_builder import (
    build_checklist_extraction_prompt,
    build_extraction_prompt,
)

_NEW_SUMMARY_FIELDS = {
    "performance_bond",
    "liquidated_damages",
    "project_duration",
    "defects_liability_period",
    "insurances",
    "clarification_deadline",
    "main_contractor",
}


def _has_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def test_new_summary_fields_present():
    names = {f.name for f in SUMMARY_FIELDS}
    assert _NEW_SUMMARY_FIELDS <= names


def test_every_summary_field_query_has_arabic_terms():
    for f in SUMMARY_FIELDS:
        assert _has_arabic(f.query), f"{f.name} query missing Arabic terms"


def test_new_categories_present():
    names = {c.name for c in CHECKLIST_CATEGORIES}
    assert "programme" in names
    assert "qaqc" in names


def test_every_category_query_has_arabic_terms():
    for c in CHECKLIST_CATEGORIES:
        assert c.queries, f"{c.name} has no queries"
        for q in c.queries:
            assert _has_arabic(q), f"{c.name} query missing Arabic terms: {q}"


def test_new_categories_follow_existing_shape():
    for c in CHECKLIST_CATEGORIES:
        if c.name in {"programme", "qaqc"}:
            assert c.display_name
            assert c.description
            assert c.prompt_hints
            assert len(c.queries) >= 2


def test_extraction_prompt_has_bilingual_verbatim_line():
    field_def = next(f for f in SUMMARY_FIELDS if f.name == "project_duration")
    prompt = build_extraction_prompt(field_def, "[SOURCE:a.pdf | PAGE:1]\nنص")
    assert "Arabic" in prompt
    assert "verbatim" in prompt


def test_checklist_prompt_has_bilingual_verbatim_line():
    category = CHECKLIST_CATEGORIES[0]
    prompt = build_checklist_extraction_prompt(category, "[SOURCE:a.pdf | PAGE:1]\nنص")
    assert "Arabic" in prompt
    assert "verbatim" in prompt
