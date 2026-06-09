import openpyxl

from app.services.offer.comparison_export import export_comparison_excel

COMPARISON = {
    "package_id": 1,
    "package_name": "HVAC Works",
    "total_offers": 2,
    "evaluated_offers": 2,
    "currency": "USD",
    "price_min": 100.0,
    "price_max": 150.0,
    "price_avg": 125.0,
    "offers": [
        {"offer_id": 1, "supplier_id": 1, "supplier_name": "CoolAir", "total_price": 100.0,
         "currency": "USD", "validity_days": 90, "delivery_weeks": 4, "payment_terms": "Net 30",
         "commercial_score": 100.0, "technical_score": 50.0, "overall_score": 75.0, "rank": 1,
         "status": "evaluated", "exclusions_count": 0, "deviations_count": 1},
        {"offer_id": 2, "supplier_id": 2, "supplier_name": "HawaCo", "total_price": 150.0,
         "currency": "USD", "validity_days": 60, "delivery_weeks": 8, "payment_terms": "Net 60",
         "commercial_score": 66.7, "technical_score": 50.0, "overall_score": 55.8, "rank": 2,
         "status": "evaluated", "exclusions_count": 1, "deviations_count": 0},
    ],
}


def test_export_writes_matrix(tmp_path):
    out = export_comparison_excel(COMPARISON, str(tmp_path / "cmp.xlsx"))
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert ws.title == "Offer Comparison"
    # header row contains the key columns
    header = [c.value for c in ws[5]]
    assert "Rank" in header and "Supplier" in header and "Overall Score" in header
    # first data row is the rank-1 supplier
    row6 = [c.value for c in ws[6]]
    assert "CoolAir" in row6
    assert 75.0 in row6
