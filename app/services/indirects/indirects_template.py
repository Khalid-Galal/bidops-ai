"""Fill a client's indirects Excel template, formula-preserving.

Rows are matched by fuzzy label similarity (Phase 11 matcher; component names
have underscores normalized to spaces). Only the detected amount column is
written; any target cell holding a formula string is skipped. Loaded with
openpyxl defaults so formulas elsewhere survive (pivot tables / VBA are not
round-tripped — .xlsm is rejected at the API layer)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from app.services.boq.sheet_select import pick_sheet
from app.services.pricing.line_item_matcher import match_score

# Priority-ordered: the FIRST alias found wins, so "description" beats "item"
# (an "Item" number column must not be mistaken for the label column) and
# "amount" beats "total" (a row-sum "Total" column must not be the write target).
_AMOUNT_ALIASES = ("amount", "value", "cost", "price", "total", "rate")
_LABEL_ALIASES = (
    "description", "particulars", "indirect item", "indirects", "indirect",
    "component", "item",
)
_MAX_HEADER_SCAN = 20
_MATCH_THRESHOLD = 0.45


def _norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def detect_columns(ws) -> tuple[int | None, int | None]:
    """Return (label_col, amount_col) from the first header row that names an
    amount-like column. Aliases are matched in PRIORITY order (not column
    order); label falls back to column 1."""
    for r in range(1, min(ws.max_row, _MAX_HEADER_SCAN) + 1):
        headers: dict[str, int] = {}
        for c in range(1, ws.max_column + 1):
            cell = _norm(ws.cell(row=r, column=c).value)
            if cell and cell not in headers:
                headers[cell] = c
        amount_col = next((headers[a] for a in _AMOUNT_ALIASES if a in headers), None)
        if amount_col is not None:
            label_col = next((headers[a] for a in _LABEL_ALIASES if a in headers), None)
            return (label_col or 1), amount_col
    return None, None


def populate_indirects_template(
    template_path: str,
    output_path: str,
    components: dict[str, float],
    *,
    amount_column: int | None = None,
    label_column: int | None = None,
) -> dict:
    """Write each component amount next to its best-matching row label.

    Each component is written at most once (best-scoring unused component per
    row, rows scanned top-down). Formula cells are never overwritten.
    Raises ValueError if no amount column can be determined.
    """
    wb = load_workbook(template_path)  # defaults preserve formulas
    try:
        ws = pick_sheet(wb)
        det_label, det_amount = detect_columns(ws)
        label_col = label_column or det_label or 1
        amount_col = amount_column or det_amount
        if amount_col is None:
            raise ValueError(
                "Could not detect an amount column in the template; "
                "pass amount_column explicitly"
            )

        remaining = dict(components)
        written = skipped_formula = 0
        for r in range(1, ws.max_row + 1):
            if not remaining:
                break
            label = ws.cell(row=r, column=label_col).value
            if label is None or str(label).strip() == "":
                continue
            label_text = str(label)
            best_name: str | None = None
            best_score = 0.0
            for name in remaining:
                # underscores are word chars to the matcher: normalize to spaces
                score = match_score(label_text, name.replace("_", " "))
                if score > best_score:
                    best_name, best_score = name, score
            if best_name is None or best_score < _MATCH_THRESHOLD:
                continue
            target = ws.cell(row=r, column=amount_col)
            if isinstance(target.value, str) and target.value.startswith("="):
                skipped_formula += 1
                remaining.pop(best_name)  # row exists but is formula-driven
                continue
            target.value = round(remaining.pop(best_name), 2)
            written += 1

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return {
            "written": written,
            "skipped_formula": skipped_formula,
            "amount_column": amount_col,
            "label_column": label_col,
            "unmatched_components": sorted(remaining),
        }
    finally:
        wb.close()
