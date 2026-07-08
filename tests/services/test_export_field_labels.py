"""FIELD_LABELS must carry a human label for every ProjectSummary field used in
exports, including the 7 fields added alongside the original 13 (performance
bond, LDs, project duration, DLP, insurances, clarification deadline, main
contractor). No DB/LLM needed -- this just checks the label dicts."""

from app.services.export.excel_export import FIELD_LABELS as EXCEL_LABELS
from app.services.export.pdf_export import FIELD_LABELS as PDF_LABELS

_NEW_FIELDS = {
    "performance_bond": "Performance Bond",
    "liquidated_damages": "Liquidated Damages",
    "project_duration": "Project Duration",
    "defects_liability_period": "Defects Liability Period",
    "insurances": "Insurances",
    "clarification_deadline": "Clarification Deadline",
    "main_contractor": "Main Contractor",
}


def test_excel_export_labels_include_new_summary_fields():
    for key, label in _NEW_FIELDS.items():
        assert EXCEL_LABELS.get(key) == label


def test_pdf_export_labels_include_new_summary_fields():
    for key, label in _NEW_FIELDS.items():
        assert PDF_LABELS.get(key) == label
