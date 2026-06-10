import pytest

from app.models.base import EmailStatus, EmailType, OfferStatus
from app.models.boq import BOQItem
from app.models.document import Document
from app.models.email import EmailLog
from app.models.historical import HistoricalPrice
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.dashboard.dashboard_service import DashboardService


async def _seed_full(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    db.add_all([
        Document(project_id=project.id, filename="a.pdf", file_path="/t/a.pdf",
                 file_type="pdf", file_size=1, status="completed"),
        Document(project_id=project.id, filename="b.pdf", file_path="/t/b.pdf",
                 file_type="pdf", file_size=1, status="failed"),
    ])
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP",
                      trade_category="mep", total_items=2, offers_received=2,
                      offers_evaluated=1)
    db.add(package)
    supplier = Supplier(name="CoolAir", emails=["s@x.test"], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    db.add_all([
        BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                description="AC", unit="no", quantity=5, client_row_index=2,
                trade_category="mep", unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, package_id=package.id, line_number="2",
                description="VRF", unit="no", quantity=2, client_row_index=3,
                trade_category="mep"),  # unpriced
        BOQItem(project_id=project.id, line_number="3", description="Excl", unit="no",
                quantity=1, client_row_index=4, unit_rate=9, total_price=9,
                is_excluded=True),
    ])
    db.add_all([
        SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.EVALUATED.value, file_paths=[], total_price=6000),
        SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                      status=OfferStatus.RECEIVED.value, file_paths=[]),
    ])
    db.add(EmailLog(package_id=package.id, supplier_id=supplier.id,
                    email_type=EmailType.RFQ.value, status=EmailStatus.DRAFT.value,
                    to=["s@x.test"], subject="RFQ", body_html="<p>x</p>"))
    db.add(HistoricalPrice(description="AC unit", rate=1000.0, source="import:x"))
    await db.commit()
    return project.id


async def test_dashboard_aggregates_counts(db_session):
    pid = await _seed_full(db_session)
    out = await DashboardService().project_dashboard(db_session, pid)
    assert out["project"]["name"] == "Metro"
    assert out["documents"] == {"total": 2, "by_status": {"completed": 1, "failed": 1}}
    assert out["boq"]["total"] == 3
    assert out["boq"]["priced"] == 1  # excluded one doesn't count
    assert out["boq"]["unpriced"] == 1
    assert out["boq"]["excluded"] == 1
    assert len(out["packages"]) == 1
    assert out["packages"][0]["code"] == "PKG-001-MEP"
    assert out["package_status_counts"] == {"draft": 1}
    assert out["offers"]["total"] == 2
    assert out["offers"]["by_status"] == {"evaluated": 1, "received": 1}
    assert out["emails"]["total"] == 1
    assert out["emails"]["by_type"] == {"rfq": 1}
    assert out["suppliers"]["total"] == 1
    assert out["pricing"]["cost_subtotal"] == 6000.0
    assert out["gaps"]["unpriced"] == 1
    assert out["historical"]["corpus_records"] == 1


async def test_dashboard_empty_project(db_session):
    project = Project(name="Empty")
    db_session.add(project)
    await db_session.commit()
    out = await DashboardService().project_dashboard(db_session, project.id)
    assert out["documents"]["total"] == 0
    assert out["boq"]["total"] == 0
    assert out["packages"] == []
    assert out["offers"]["total"] == 0
    assert out["pricing"]["cost_subtotal"] == 0.0


async def test_dashboard_unknown_project(db_session):
    with pytest.raises(ValueError):
        await DashboardService().project_dashboard(db_session, 999999)
