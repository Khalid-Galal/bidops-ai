"""Rule-based document classifier: filename keywords first, text fallback.

Keywords come from rules.classification.document_categories; dict order is
match precedence (addendum is listed first so 'Addendum 3 - revised specs'
classifies as addendum, not specs). Deterministic — no LLM.
"""

from __future__ import annotations

import re

_FILENAME_CONFIDENCE = 0.9
_TEXT_CONFIDENCE = 0.6
_TEXT_SAMPLE_CHARS = 2000

_SEP = re.compile(r"[\s_\-.()/]+")


def _tokens(text):
    return set(t for t in _SEP.split(text.lower()) if t)


def _matches(keyword, text, tokens):
    """Single-word keywords match a tokenized set; multi-word (contains a
    space) keywords match a separator-normalized substring."""
    kw = keyword.lower()
    if " " in kw:
        return kw in _SEP.sub(" ", text.lower())
    return kw in tokens


def classify_document(filename: str, text: str | None, rules) -> tuple[str, float]:
    """Return (category, confidence). 'general' / 0.0 when nothing matches."""
    categories = rules.classification.document_categories
    name = filename or ""
    name_tokens = _tokens(name)
    for category, keywords in categories.items():
        if any(_matches(kw, name, name_tokens) for kw in keywords):
            return category, _FILENAME_CONFIDENCE
    sample = (text or "")[:_TEXT_SAMPLE_CHARS]
    if sample:
        text_tokens = _tokens(sample)
        for category, keywords in categories.items():
            if any(_matches(kw, sample, text_tokens) for kw in keywords):
                return category, _TEXT_CONFIDENCE
    return "general", 0.0
