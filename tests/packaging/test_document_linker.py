from dataclasses import dataclass


@dataclass
class FakeHit:
    document_id: int
    score: float
    text: str
    page_number: int | None = 1
    filename: str = "doc.pdf"


class FakeSearch:
    """Stand-in for HybridSearchService: returns canned hits regardless of query."""

    def __init__(self, hits):
        self._hits = hits
        self.calls = []

    def search(self, project_id, query, top_k=10, mode="hybrid"):
        self.calls.append((project_id, query, mode))
        return self._hits


def _doc(project_id, filename):
    """Build a Document with all NOT NULL columns populated."""
    from app.models.document import Document

    return Document(
        project_id=project_id,
        filename=filename,
        file_path=f"/tmp/{filename}",
        file_type="pdf",
        file_size=1,
    )


async def _seed(db):
    from app.models.project import Project
    from app.models.package import Package
    from app.models.boq import BOQItem

    project = Project(name="P")
    db.add(project)
    await db.flush()
    # two documents
    d1 = _doc(project.id, "concrete_spec.pdf")
    d2 = _doc(project.id, "hvac_spec.pdf")
    db.add_all([d1, d2])
    await db.flush()
    pkg = Package(project_id=project.id, name="Concrete Works",
                  code="PKG-P0001-CON-001", trade_category="concrete", total_items=1)
    db.add(pkg)
    await db.flush()
    db.add(BOQItem(project_id=project.id, package_id=pkg.id, line_number="1",
                   description="Reinforced concrete C35/45", unit="m3", quantity=10,
                   client_row_index=1, trade_category="concrete"))
    await db.commit()
    return project.id, pkg, d1.id, d2.id


async def test_link_package_aggregates_hits_per_document(db_session):
    from sqlalchemy import select
    from app.models.package import PackageDocument
    from app.services.packaging.document_linker import DocumentLinker

    pid, pkg, d1, d2 = await _seed(db_session)
    # d1 has two strong chunks, d2 one weaker chunk
    search = FakeSearch([
        FakeHit(d1, 0.91, "Concrete grade C35/45 to BS 8500", 12, "concrete_spec.pdf"),
        FakeHit(d1, 0.77, "Formwork tolerances", 13, "concrete_spec.pdf"),
        FakeHit(d2, 0.40, "HVAC duct insulation", 4, "hvac_spec.pdf"),
    ])
    linker = DocumentLinker(search_service=search)

    n = await linker.link_package(db_session, pkg, min_score=0.5, max_docs=10)
    assert n == 1                       # only d1 clears min_score 0.5
    links = (await db_session.execute(
        select(PackageDocument).where(PackageDocument.package_id == pkg.id)
    )).scalars().all()
    assert len(links) == 1
    link = links[0]
    assert link.document_id == d1
    assert abs(link.relevance_score - 0.91) < 1e-9   # max chunk score
    assert "C35/45" in link.excerpt                  # best chunk excerpt
    # query was built from trade + item description
    assert any("concrete" in q.lower() for (_, q, _) in search.calls)


async def test_link_package_is_idempotent(db_session):
    from sqlalchemy import select, func
    from app.models.package import PackageDocument
    from app.services.packaging.document_linker import DocumentLinker

    pid, pkg, d1, d2 = await _seed(db_session)
    search = FakeSearch([FakeHit(d1, 0.9, "x", 1, "concrete_spec.pdf")])
    linker = DocumentLinker(search_service=search)
    await linker.link_package(db_session, pkg)
    await linker.link_package(db_session, pkg)   # re-link
    count = (await db_session.execute(
        select(func.count()).select_from(PackageDocument).where(
            PackageDocument.package_id == pkg.id)
    )).scalar_one()
    assert count == 1                            # not duplicated


async def test_link_all_links_every_package(db_session):
    from app.models.package import PackageDocument  # noqa: F401
    from app.services.packaging.document_linker import DocumentLinker

    pid, pkg, d1, d2 = await _seed(db_session)
    search = FakeSearch([FakeHit(d1, 0.8, "concrete spec", 1, "concrete_spec.pdf")])
    result = await DocumentLinker(search_service=search).link_all(db_session, pid)
    assert result["packages"] == 1
    assert result["links_created"] == 1


async def test_analyze_then_linker_excludes(db_session):
    """End-to-end: VersioningService.analyze() marks the older revision, then the
    linker (given hits for BOTH) links only the surviving revision."""
    from sqlalchemy import select

    from app.models.boq import BOQItem
    from app.models.document import Document
    from app.models.package import Package, PackageDocument
    from app.models.project import Project
    from app.services.packaging.document_linker import DocumentLinker
    from app.services.versioning.versioning_service import VersioningService

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    rev_a = Document(project_id=project.id, filename="Spec_RevA.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="spec rev a")
    rev_b = Document(project_id=project.id, filename="Spec_RevB.pdf", file_path="/m",
                     file_type="pdf", file_size=1, extracted_text="spec rev b")
    db_session.add_all([rev_a, rev_b])
    await db_session.flush()
    pkg = Package(project_id=project.id, name="Specs", code="PKG-1",
                  trade_category="specs", total_items=1)
    db_session.add(pkg)
    await db_session.flush()
    db_session.add(BOQItem(project_id=project.id, package_id=pkg.id, line_number="1",
                           description="Technical specification clause", unit="no",
                           quantity=1, client_row_index=1, trade_category="specs"))
    await db_session.commit()

    await VersioningService().analyze(db_session, project.id)
    await db_session.refresh(rev_a)
    await db_session.refresh(rev_b)
    assert rev_a.is_superseded is True
    assert rev_b.is_superseded is False

    search = FakeSearch([
        FakeHit(rev_a.id, 0.95, "spec rev a section", 1, "Spec_RevA.pdf"),
        FakeHit(rev_b.id, 0.90, "spec rev b section", 1, "Spec_RevB.pdf"),
    ])
    created = await DocumentLinker(search_service=search).link_package(db_session, pkg)
    assert created == 1
    links = (await db_session.execute(
        select(PackageDocument).where(PackageDocument.package_id == pkg.id)
    )).scalars().all()
    assert [l.document_id for l in links] == [rev_b.id]  # only the live revision


async def test_link_package_skips_superseded_documents(db_session):
    from dataclasses import dataclass

    from app.models.boq import BOQItem
    from app.models.document import Document
    from app.models.package import Package, PackageDocument
    from app.models.project import Project
    from app.services.packaging.document_linker import DocumentLinker
    from sqlalchemy import select

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-1", trade_category="mep")
    db_session.add(package)
    live = Document(project_id=project.id, filename="Spec_RevB.pdf", file_path="/m",
                    file_type="pdf", file_size=1)
    stale = Document(project_id=project.id, filename="Spec_RevA.pdf", file_path="/m",
                     file_type="pdf", file_size=1, is_superseded=True,
                     supersede_reason="auto:superseded by newer revision")
    db_session.add_all([live, stale])
    await db_session.flush()
    db_session.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                           description="AC unit", unit="no", quantity=1,
                           client_row_index=2, trade_category="mep"))
    await db_session.commit()

    @dataclass
    class Hit:
        document_id: int
        score: float
        text: str
        page_number: int = 1

    class FakeSearch:
        def search(self, project_id, query, top_k=10, mode="hybrid"):
            return [Hit(live.id, 0.9, "live spec"), Hit(stale.id, 0.95, "stale spec")]

    linker = DocumentLinker(search_service=FakeSearch())
    created = await linker.link_package(db_session, package)
    assert created == 1
    links = (await db_session.execute(
        select(PackageDocument).where(PackageDocument.package_id == package.id)
    )).scalars().all()
    assert [l.document_id for l in links] == [live.id]  # stale doc excluded
