"""Shared commercial (markup + VAT) computation over a cost base.

Single source of truth for the markup/VAT formula so pricing_summary (base =
direct cost) and the indirects cost-summary (base = direct + indirects) cannot
diverge. All values are configurable via rules.commercial.
"""

from __future__ import annotations


def compute_commercial(base: float, rules) -> dict:
    """Apply rules.commercial markups + VAT to a cost base.

    markup_total = base * sum(overhead, profit, contingency, risk)
    selling_before_vat = base + markup_total
    vat_amount = selling_before_vat * vat_rate
    grand_total = selling_before_vat + vat_amount
    """
    m = rules.commercial.markup
    overhead = round(base * m.overhead, 2)
    profit = round(base * m.profit, 2)
    contingency = round(base * m.contingency, 2)
    risk = round(base * m.risk, 2)
    markup_total = round(overhead + profit + contingency + risk, 2)
    selling_before_vat = round(base + markup_total, 2)
    vat_rate = rules.commercial.vat_rate
    vat_amount = round(selling_before_vat * vat_rate, 2)
    grand_total = round(selling_before_vat + vat_amount, 2)
    return {
        "markups": {
            "overhead": overhead,
            "profit": profit,
            "contingency": contingency,
            "risk": risk,
            "markup_total": markup_total,
        },
        "selling_before_vat": selling_before_vat,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
    }
