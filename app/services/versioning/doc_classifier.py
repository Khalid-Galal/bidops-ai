"""Rule-based document classifier: filename keywords first, text fallback.

Keywords come from rules.classification.document_categories; dict order is
match precedence (addendum is listed first so 'Addendum 3 - revised specs'
classifies as addendum, not specs). Deterministic — no LLM.
"""

from __future__ import annotations

_FILENAME_CONFIDENCE = 0.9
_TEXT_CONFIDENCE = 0.6
_TEXT_SAMPLE_CHARS = 2000


def classify_document(filename: str, text: str | None, rules) -> tuple[str, float]:
    """Return (category, confidence). 'general' / 0.0 when nothing matches."""
    categories = rules.classification.document_categories
    name = (filename or "").lower()
    for category, keywords in categories.items():
        if any(kw.lower() in name for kw in keywords):
            return category, _FILENAME_CONFIDENCE
    sample = (text or "")[:_TEXT_SAMPLE_CHARS].lower()
    if sample:
        for category, keywords in categories.items():
            if any(kw.lower() in sample for kw in keywords):
                return category, _TEXT_CONFIDENCE
    return "general", 0.0
