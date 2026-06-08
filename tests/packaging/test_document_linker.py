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
