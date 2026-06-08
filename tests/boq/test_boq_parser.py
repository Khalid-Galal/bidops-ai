import json
from pathlib import Path

from openpyxl import Workbook

from app.schemas.rules import RulesConfig


def _default_rules() -> RulesConfig:
    """Load the committed default rules (unit_mappings live in the JSON, not the
    RulesConfig() empty defaults)."""
    return RulesConfig.model_validate(
        json.loads(Path("config/rules.default.json").read_text(encoding="utf-8"))
    )


def _make_boq(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Title row spanning the sheet", None, None, None])  # noise row 1
    ws.append(["Item", "Description", "Unit", "Qty"])              # header row 2
    ws.append([None, "DIVISION 2 - CONCRETE WORKS", None, None])   # section (no qty)
    ws.append(["2.1", "Reinforced concrete C35/45 in columns", "cum", 5400])
    ws.append(["2.2", "High-tensile reinforcement steel", "ton", 4900])
    ws.append([None, "DIVISION 3 - HVAC", None, None])             # section
    ws.append(["3.1", "Supply and install AHU with HEPA filter", "nr", 22])
    wb.save(path)


def test_parse_detects_header_sections_units(tmp_path):
    from app.services.boq.boq_parser import parse_boq_workbook

    f = tmp_path / "boq.xlsx"
    _make_boq(f)
    rows = parse_boq_workbook(str(f), _default_rules())

    # 3 priced items (section rows excluded)
    assert len(rows) == 3
    first = rows[0]
    assert first.description.startswith("Reinforced concrete")
    assert first.unit == "m3"            # "cum" standardized via unit_mappings
    assert first.quantity == 5400
    assert first.section == "DIVISION 2 - CONCRETE WORKS"
    assert rows[2].section == "DIVISION 3 - HVAC"
    assert rows[2].unit == "no"          # "nr" -> "no"
    assert rows[0].client_row_index == 4  # 1-based Excel row of the item
