"""Deterministic fuzzy matching of BOQ item descriptions to offer line items.

No LLM/embeddings — combines token-set Jaccard with difflib's sequence ratio.
An optional semantic_scorer(a, b) -> float can be injected to blend in an
embedding-based score (the seam for a future semantic upgrade); when absent the
matcher is fully deterministic and dependency-free.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Default match threshold for accepting a BOQ<->offer line-item pairing, and the
# confidence above which a populated price is NOT flagged for review.
DEFAULT_THRESHOLD = 0.45
HIGH_CONFIDENCE = 0.7

_PUNCT = re.compile(r"[^\w\s]")


def normalize_desc(text: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    cleaned = _PUNCT.sub(" ", str(text).lower())
    return " ".join(cleaned.split())


def match_score(a: str | None, b: str | None) -> float:
    """Similarity in [0, 1]: mean of token-set Jaccard and difflib ratio."""
    na, nb = normalize_desc(a), normalize_desc(b)
    if not na or not nb:
        return 0.0
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb)
    ratio = SequenceMatcher(None, na, nb).ratio()
    return round((jaccard + ratio) / 2.0, 4)


def best_match(
    query: str,
    candidates: list[dict],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    semantic_scorer=None,
    key: str = "description",
) -> tuple[dict | None, float]:
    """Return (best candidate, score) if score >= threshold, else (None, score)."""
    best: dict | None = None
    best_score = 0.0
    for cand in candidates:
        cand_desc = cand.get(key, "") if isinstance(cand, dict) else getattr(cand, key, "")
        score = match_score(query, cand_desc)
        if semantic_scorer is not None:
            score = max(score, float(semantic_scorer(query, cand_desc)))
        if score > best_score:
            best_score = score
            best = cand
    if best_score >= threshold:
        return best, round(best_score, 4)
    return None, round(best_score, 4)
