"""Shared sheet-selection logic for BOQ workbooks.

Both the parser (which reads BOQ rows) and the template writer (which writes
rates back) MUST pick the same worksheet, or rates would land in a different
sheet than the one parsed. Keeping the logic here guarantees they cannot
diverge.
"""

from __future__ import annotations

# Substrings (lowercased) that hint a sheet is the priced BOQ.
SHEET_HINTS = ("boq", "bill", "quantity", "pricing", "boqs")


def pick_sheet(wb):
    """Return the worksheet whose name hints at a BOQ, else the first sheet."""
    for name in wb.sheetnames:
        if any(h in name.lower() for h in SHEET_HINTS):
            return wb[name]
    return wb[wb.sheetnames[0]]
