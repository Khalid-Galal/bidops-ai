"""Render an offer-comparison matrix to an .xlsx workbook (openpyxl)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HEADERS = [
    "Rank", "Supplier", "Total Price", "Currency", "Validity (days)",
    "Delivery (weeks)", "Payment Terms", "Commercial Score", "Technical Score",
    "Overall Score", "Status", "Exclusions", "Deviations",
]
_WIDTHS = [6, 28, 14, 9, 14, 16, 18, 16, 16, 14, 14, 11, 11]


def build_comparison_workbook(comparison: dict) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Offer Comparison"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    best_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    border = Border(left=Side(style="thin"), right=Side(style="thin"),
                    top=Side(style="thin"), bottom=Side(style="thin"))

    last_col = get_column_letter(len(_HEADERS))
    ws.merge_cells(f"A1:{last_col}1")
    ws["A1"] = f"Offer Comparison - {comparison.get('package_name', '')}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A3"] = "Total Offers:"
    ws["B3"] = comparison.get("total_offers", 0)
    ws["C3"] = "Lowest Price:"
    ws["D3"] = comparison.get("price_min")
    ws["E3"] = comparison.get("currency", "")

    for col, header in enumerate(_HEADERS, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center")

    for row_idx, offer in enumerate(comparison.get("offers", []), 6):
        values = [
            offer.get("rank") or "-",
            offer.get("supplier_name") or "",
            offer.get("total_price") if offer.get("total_price") is not None else "-",
            offer.get("currency") or "",
            offer.get("validity_days") if offer.get("validity_days") is not None else "-",
            offer.get("delivery_weeks") if offer.get("delivery_weeks") is not None else "-",
            offer.get("payment_terms") or "-",
            round(offer.get("commercial_score") or 0, 1),
            round(offer.get("technical_score") or 0, 1),
            round(offer.get("overall_score") or 0, 1),
            offer.get("status") or "",
            offer.get("exclusions_count", 0),
            offer.get("deviations_count", 0),
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border = border
            if offer.get("rank") == 1:
                cell.fill = best_fill

    for col, width in enumerate(_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return wb


def export_comparison_excel(comparison: dict, output_path: str) -> str:
    wb = build_comparison_workbook(comparison)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
