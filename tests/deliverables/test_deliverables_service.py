import json
from pathlib import Path

import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.deliverables.deliverables_service import DeliverablesService


async def _seed(db, tmp_path):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    brief = tmp_path / "brief.html"
    brief.write_text("<h1>Brief</h1>")
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                      trade_category="mep", brief_path=str(brief))
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=[], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    db.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                   description="AC", unit="no", quantity=5, client_row_index=2,
                   trade_category="mep", unit_rate=1200, total_price=6000, currency="USD"))
    db.add(SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                         status=OfferStatus.EVALUATED.value, file_paths=[],
                         total_price=6000, currency="USD", overall_score=75.0, rank=1))
    await db.commit()
    return project.id


async def test_build_assembles_deliverables(db_session, tmp_path):
    pid = await _seed(db_session, tmp_path)
    svc = DeliverablesService(output_root=tmp_path / "deliv")
    result = await svc.build(db_session, pid)
    folder = Path(result["folder"])
    names = set(result["files"])
    assert "Pricing_Summary.xlsx" in names
    assert "Pricing_Gaps.xlsx" in names
    assert "Comparison_PKG-001-MEP.xlsx" in names
    assert "manifest.json" in names
    assert (folder / "Briefs" / "brief.html").exists()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_id"] == pid
    assert manifest["project_name"] == "Metro"
    assert "generated_at" in manifest


async def test_build_is_idempotent(db_session, tmp_path):
    pid = await _seed(db_session, tmp_path)
    svc = DeliverablesService(output_root=tmp_path / "deliv")
    first = await svc.build(db_session, pid)
    second = await svc.build(db_session, pid)
    assert sorted(first["files"]) == sorted(second["files"])
    # no leftover duplicates from the first build
    folder = Path(second["folder"])
    assert len(list(folder.rglob("*.xlsx"))) == len(
        [f for f in second["files"] if f.endswith(".xlsx")]
    )


async def test_build_unknown_project(db_session, tmp_path):
    with pytest.raises(ValueError):
        await DeliverablesService(output_root=tmp_path).build(db_session, 999999)
