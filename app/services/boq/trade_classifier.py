"""Deterministic trade classification from the configurable rules keyword map."""

from __future__ import annotations

from app.schemas.rules import RulesConfig


def classify_trade(description: str, rules: RulesConfig) -> tuple[str | None, float]:
    """Classify a BOQ description into a trade category.

    Matches keywords from rules.packaging.trade_categories (case-insensitive,
    substring). Returns (category, confidence) where confidence scales with the
    number of distinct keyword hits (capped at 1.0). Unmatched -> (None, 0.0),
    which downstream marks the item as requiring review.
    """
    text = description.lower()
    best_cat: str | None = None
    best_hits = 0
    for category, keywords in rules.packaging.trade_categories.items():
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = category
    if best_cat is None:
        return None, 0.0
    # 1 hit -> 0.6, 2 -> 0.8, 3+ -> capped near 1.0
    confidence = min(1.0, 0.4 + 0.2 * best_hits)
    return best_cat, round(confidence, 3)
