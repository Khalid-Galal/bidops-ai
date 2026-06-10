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
    assert (folder / "Briefs" / "PKG-001-MEP_brief.html").exists()
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


async def test_register_copied_when_present(db_session, tmp_path):
    import openpyxl

    from app.services.packaging.package_exporter import PackageExporter

    pid = await _seed(db_session, tmp_path)
    exporter = PackageExporter(output_root=tmp_path / "pkgs")
    register = exporter.register_path(pid)
    register.parent.mkdir(parents=True)
    wb = openpyxl.Workbook()
    wb.active.append(["Code", "Name"])
    wb.save(register)

    svc = DeliverablesService(
        output_root=tmp_path / "deliv", package_exporter=exporter
    )
    result = await svc.build(db_session, pid)
    assert "Packages_Register.xlsx" in result["files"]
    assert (Path(result["folder"]) / "Packages_Register.xlsx").exists()


async def test_build_duration_plumbs_through(db_session, tmp_path, monkeypatch):
    import app.services.deliverables.deliverables_service as ds_mod
    from app.schemas.rules import DurationBasedRole, RulesConfig
    from app.services.indirects.indirects_service import IndirectsService

    pid = await _seed(db_session, tmp_path)

    rules = RulesConfig()  # percentage_based defaults to {}
    rules.indirects.duration_based = {
        "project_manager": DurationBasedRole(monthly_rate=5000)
    }

    class _FakeRulesService:
        def load(self):
            return rules

    monkeypatch.setattr(
        ds_mod, "IndirectsService",
        lambda: IndirectsService(rules_service=_FakeRulesService()),
    )

    svc = DeliverablesService(output_root=tmp_path / "deliv")
    result = await svc.build(db_session, pid, duration_months=6)
    manifest = json.loads(
        (Path(result["folder"]) / "manifest.json").read_text(encoding="utf-8")
    )
    # direct 6000 + duration indirects 6*5000=30000 -> base 36000 -> *1.26
    assert manifest["grand_total"] == 45360.0
    assert manifest["duration_months"] == 6


async def test_briefs_do_not_collide(db_session, tmp_path):
    """Two packages whose brief files share a basename must BOTH survive the
    flatten into Briefs/ (regression: the second copy silently overwrote the
    first)."""
    project = Project(name="Collide")
    db_session.add(project)
    await db_session.flush()
    brief_a = tmp_path / "pkg_a" / "Package_Brief.html"
    brief_a.parent.mkdir()
    brief_a.write_text("<h1>Alpha brief</h1>")
    brief_b = tmp_path / "pkg_b" / "Package_Brief.html"
    brief_b.parent.mkdir()
    brief_b.write_text("<h1>Bravo brief</h1>")
    db_session.add(Package(project_id=project.id, name="Concrete", code="PKG-001-CON",
                           trade_category="concrete", brief_path=str(brief_a)))
    db_session.add(Package(project_id=project.id, name="HVAC", code="PKG-002-MEP",
                           trade_category="mep", brief_path=str(brief_b)))
    await db_session.commit()

    svc = DeliverablesService(output_root=tmp_path / "deliv")
    result = await svc.build(db_session, project.id)

    briefs_dir = Path(result["folder"]) / "Briefs"
    copies = sorted(briefs_dir.iterdir())
    assert len(copies) == 2
    assert result["briefs"] == 2
    assert len(result["files"]) == len(set(result["files"]))  # no duplicate entries
    contents = {p.read_text() for p in copies}
    assert contents == {"<h1>Alpha brief</h1>", "<h1>Bravo brief</h1>"}
