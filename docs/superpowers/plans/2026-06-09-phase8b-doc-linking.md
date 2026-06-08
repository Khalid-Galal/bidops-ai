# Phase 8B — Link Documents to Packages (semantic) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For each generated package, find the relevant project documents (specs/drawings/ITT sections) via semantic search over the indexed chunks and persist `PackageDocument` links with relevance scores + excerpts, exposed through a link API and the package detail view.

**Architecture:** A `DocumentLinker` builds a search query from a package's trade + representative BOQ item descriptions, runs the existing hybrid search service (semantic mode) over the project's ChromaDB collection, aggregates chunk hits per `document_id` (max score + best excerpt), and writes `PackageDocument` rows (Phase 6A) — idempotently per package. The search dependency is **injectable**: tests pass a fake search (no ChromaDB/embedding-model load); production lazily resolves the real `HybridSearchService`. API: `POST /packages/link-documents` (link all packages in a project) and the package detail now returns its linked documents.

**Tech Stack:** Python 3.11, async SQLAlchemy, FastAPI, httpx (ASGI tests), pytest. (ChromaDB/sentence-transformers only at runtime, not in tests.)

**Reference:** `bidops-ai/backend/app/services/packaging_service.py::link_documents_to_package` (search per package, average scores per doc). Adapt to the root search service + models.

**Decomposition note:** Plan **8B** of Phase 8 (after 8A generation). Sibling: **8C** package folder structure + Packages Register + Brief PDF. Consumes 6A (`Package`/`PackageDocument`/`Document`/`BOQItem`), the existing search service (`app/services/search/hybrid_search.py`, results carry `document_id/score/text/page_number/filename`).

---

## File Structure

- `app/services/packaging/document_linker.py` — CREATE: `DocumentLinker` (injectable search; `link_package`, `link_all`, query builder).
- `app/schemas/packaging.py` — MODIFY: add `LinkedDocumentResponse`; add `linked_documents` to `PackageDetailResponse`.
- `app/api/packaging.py` — MODIFY: add `POST /link-documents`; include linked documents in detail.
- `tests/packaging/test_document_linker.py` — CREATE: unit tests with a fake search.
- `tests/packaging/test_packaging_api.py` — MODIFY: add a link-documents API test (inject fake search).

---

## Task 1: `DocumentLinker` (injectable search → PackageDocument rows)

**Files:** Create `app/services/packaging/document_linker.py`; Test `tests/packaging/test_document_linker.py`

- [ ] **Step 1: Write the failing test `tests/packaging/test_document_linker.py`**

```python
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


async def _seed(db):
    from app.models.project import Project
    from app.models.document import Document
    from app.models.package import Package
    from app.models.boq import BOQItem

    project = Project(name="P")
    db.add(project)
    await db.flush()
    # two documents
    d1 = Document(project_id=project.id, filename="concrete_spec.pdf")
    d2 = Document(project_id=project.id, filename="hvac_spec.pdf")
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
    from app.models.package import PackageDocument
    from app.services.packaging.document_linker import DocumentLinker
    from sqlalchemy import select, func

    pid, pkg, d1, d2 = await _seed(db_session)
    search = FakeSearch([FakeHit(d1, 0.8, "concrete spec", 1, "concrete_spec.pdf")])
    result = await DocumentLinker(search_service=search).link_all(db_session, pid)
    assert result["packages"] == 1
    assert result["links_created"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_document_linker.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create `app/services/packaging/document_linker.py`**

```python
"""Links project documents to packages via semantic search over indexed chunks."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.package import Package, PackageDocument

_EXCERPT_LEN = 300
_DEFAULT_TOP_K = 30
_DEFAULT_MIN_SCORE = 0.3
_DEFAULT_MAX_DOCS = 10
_QUERY_ITEM_SAMPLE = 8  # BOQ item descriptions to fold into the query


class DocumentLinker:
    """Find and persist the documents most relevant to each package.

    The search dependency is injectable so the aggregation/persistence logic is
    testable without ChromaDB; production lazily resolves the real service.
    """

    def __init__(self, search_service=None) -> None:
        self._injected = search_service

    def _search(self):
        if self._injected is not None:
            return self._injected
        from app.api.search import _get_search_service

        return _get_search_service()

    async def _build_query(self, db: AsyncSession, package: Package) -> str:
        descs = (
            await db.execute(
                select(BOQItem.description)
                .where(BOQItem.package_id == package.id)
                .limit(_QUERY_ITEM_SAMPLE)
            )
        ).scalars().all()
        trade = (package.trade_category or "").replace("_", " ")
        return f"{trade} specifications drawings requirements " + " ".join(descs)

    async def link_package(
        self,
        db: AsyncSession,
        package: Package,
        *,
        top_k: int = _DEFAULT_TOP_K,
        min_score: float = _DEFAULT_MIN_SCORE,
        max_docs: int = _DEFAULT_MAX_DOCS,
    ) -> int:
        """(Re)link the most relevant documents to a package. Returns link count."""
        query = await self._build_query(db, package)
        try:
            hits = self._search().search(
                project_id=package.project_id, query=query, top_k=top_k, mode="semantic"
            )
        except Exception:  # noqa: BLE001 - search infra failure -> no links, not a crash
            hits = []

        # Aggregate hits per document: keep max score + its best excerpt/page.
        best: dict[int, dict] = {}
        for h in hits:
            doc_id = getattr(h, "document_id", None)
            if doc_id is None:
                continue
            score = float(getattr(h, "score", 0.0) or 0.0)
            cur = best.get(doc_id)
            if cur is None or score > cur["score"]:
                best[doc_id] = {
                    "score": score,
                    "excerpt": (getattr(h, "text", "") or "")[:_EXCERPT_LEN],
                    "page": getattr(h, "page_number", None),
                    "hits": (cur["hits"] + 1) if cur else 1,
                }
            elif cur:
                cur["hits"] += 1

        selected = sorted(
            ((d, v) for d, v in best.items() if v["score"] >= min_score),
            key=lambda kv: kv[1]["score"],
            reverse=True,
        )[:max_docs]

        # Idempotent: clear existing links for this package first.
        await db.execute(
            delete(PackageDocument).where(PackageDocument.package_id == package.id)
        )

        trade = package.trade_category or "package"
        for doc_id, v in selected:
            db.add(
                PackageDocument(
                    package_id=package.id,
                    document_id=doc_id,
                    relevance_score=round(v["score"], 4),
                    relevance_reason=f"{v['hits']} relevant section(s) for {trade}",
                    excerpt=v["excerpt"],
                    page_ranges=[[v["page"], v["page"]]] if v["page"] else None,
                )
            )
        await db.commit()
        return len(selected)

    async def link_all(self, db: AsyncSession, project_id: int) -> dict:
        """Link documents for every package in a project."""
        packages = (
            await db.execute(
                select(Package).where(Package.project_id == project_id)
            )
        ).scalars().all()
        total = 0
        for package in packages:
            total += await self.link_package(db, package)
        return {"project_id": project_id, "packages": len(packages), "links_created": total}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_document_linker.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/packaging/document_linker.py tests/packaging/test_document_linker.py
git commit -m "feat(packaging): DocumentLinker — semantic doc->package linking (injectable search)"
```

---

## Task 2: API — link-documents + linked docs in detail

**Files:** Modify `app/schemas/packaging.py`, `app/api/packaging.py`; Test add to `tests/packaging/test_packaging_api.py`

- [ ] **Step 1: Add the failing API test to `tests/packaging/test_packaging_api.py`**

Add at the end (reuses the existing `pkg_client` fixture; injects a fake search into the linker via monkeypatch):

```python
async def test_link_documents_and_detail_shows_links(pkg_client, monkeypatch):
    from dataclasses import dataclass
    import app.api.packaging as pkg_api

    client, pid = pkg_client

    # Seed a document to link to (the fixture engine is reachable via get_db override;
    # insert through the same factory by issuing a normal request path is awkward, so
    # link against whatever documents exist — here we fake search hits referencing a
    # document we create via the override session).
    @dataclass
    class FakeHit:
        document_id: int
        score: float
        text: str
        page_number: int = 1
        filename: str = "spec.pdf"

    class FakeSearch:
        def __init__(self, hits): self._hits = hits
        def search(self, project_id, query, top_k=10, mode="hybrid"): return self._hits

    # Create a document row + capture its id via the app's own DB session override.
    from app.database import get_db
    gen = pkg_api  # ensure module imported
    # Pull a session from the overridden dependency
    override = client._transport.app.dependency_overrides[get_db]
    agen = override()
    session = await agen.__anext__()
    from app.models.document import Document
    doc = Document(project_id=pid, filename="concrete_spec.pdf")
    session.add(doc)
    await session.commit()
    doc_id = doc.id
    await agen.aclose()

    # Force the linker to use a fake search returning a hit for that document.
    monkeypatch.setattr(
        pkg_api, "DocumentLinker",
        lambda: __import__("app.services.packaging.document_linker", fromlist=["DocumentLinker"]).DocumentLinker(
            search_service=FakeSearch([FakeHit(doc_id, 0.88, "Concrete C35/45 spec", 7)])
        ),
    )

    async with client:
        await client.post(f"/api/projects/{pid}/packages/generate")
        link = await client.post(f"/api/projects/{pid}/packages/link-documents")
        assert link.status_code == 200, link.text
        assert link.json()["links_created"] >= 1

        packages = (await client.get(f"/api/projects/{pid}/packages")).json()
        concrete = next(p for p in packages if p["trade_category"] == "concrete")
        detail = (await client.get(f"/api/projects/{pid}/packages/{concrete['id']}")).json()
        assert any(ld["document_id"] == doc_id for ld in detail["linked_documents"])
        assert detail["linked_documents"][0]["filename"] == "concrete_spec.pdf"
```

Note: if reaching into `client._transport.app` is brittle in your httpx version, instead import `app.main.app` directly and read `app.dependency_overrides[get_db]` (same object the fixture set). Keep the intent: seed a `Document` in the override DB, inject a fake search hit for it, link, and assert the detail shows it.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py::test_link_documents_and_detail_shows_links -v`
Expected: FAIL (no `/link-documents` route, no `linked_documents` in detail).

- [ ] **Step 3: Extend `app/schemas/packaging.py`**

Add:

```python
class LinkedDocumentResponse(BaseModel):
    document_id: int
    filename: str
    relevance_score: float | None
    relevance_reason: str | None
    excerpt: str | None
```

And add to `PackageDetailResponse`:

```python
    linked_documents: list[LinkedDocumentResponse] = []
```

Also add a link-result schema:

```python
class DocumentLinkResult(BaseModel):
    project_id: int
    packages: int
    links_created: int
```

- [ ] **Step 4: Extend `app/api/packaging.py`**

Add the import:
```python
from sqlalchemy import select
from app.models.document import Document
from app.models.package import PackageDocument
from app.services.packaging.document_linker import DocumentLinker
from app.schemas.packaging import DocumentLinkResult, LinkedDocumentResponse
```

Add the link endpoint:
```python
@router.post("/link-documents", response_model=DocumentLinkResult)
async def link_documents(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentLinkResult:
    """Link the most relevant documents to each package via semantic search."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await DocumentLinker().link_all(db, project_id)
    return DocumentLinkResult(**summary)
```

In `package_detail`, after building `detail`, attach linked documents (join `PackageDocument` + `Document` for filename):
```python
    rows = (
        await db.execute(
            select(PackageDocument, Document.filename)
            .join(Document, Document.id == PackageDocument.document_id)
            .where(PackageDocument.package_id == package_id)
            .order_by(PackageDocument.relevance_score.desc())
        )
    ).all()
    detail.linked_documents = [
        LinkedDocumentResponse(
            document_id=pd.document_id,
            filename=filename,
            relevance_score=pd.relevance_score,
            relevance_reason=pd.relevance_reason,
            excerpt=pd.excerpt,
        )
        for pd, filename in rows
    ]
```

(The `DocumentLinker` reference in the endpoint must be module-level importable so the test can monkeypatch `app.api.packaging.DocumentLinker`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py -v`
Expected: PASS (all packaging API tests, incl. the new link test).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/packaging.py app/api/packaging.py tests/packaging/test_packaging_api.py
git commit -m "feat(packaging): POST /link-documents + linked documents in package detail"
```

---

## Task 3: Full-suite check

- [ ] **Step 1: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (… + 8B). Report the count.

- [ ] **Step 2: Boot smoke**

Run: `.venv/Scripts/python.exe -c "import app.main; print('link route:', [r.path for r in app.main.app.routes if 'link-documents' in getattr(r,'path','')])"`
Expected: shows `/api/projects/{project_id}/packages/link-documents`.

---

## Self-Review (completed by author)

- **Spec coverage:** Implements plan.md capability 4's document-linking aspect: per-package semantic retrieval over indexed chunks, aggregated per document with relevance score + excerpt, persisted as `PackageDocument`, surfaced via link API + package detail. Idempotent per package. Search failure degrades to zero links (never crashes ingestion/linking).
- **Out of scope (8C):** folder structure, Packages Register.xlsx, Package Brief PDF.
- **Testability:** the search dependency is injectable; unit tests use a fake search (no ChromaDB/model load). The API test injects a fake search via monkeypatching the module-level `DocumentLinker` and seeds a real `Document` in the override DB.
- **Placeholder scan:** Complete code for the linker, schemas, API edits, and tests. The API test notes a fallback if `client._transport.app` access is brittle (use `app.main.app` directly) — both paths reach the same override object; the executor picks whichever works in the installed httpx.
- **Type consistency:** `DocumentLinker.link_package(db, package, *, top_k, min_score, max_docs)` and `link_all(db, project_id)` consistent across service, API, tests. Search hits read by attribute (`document_id/score/text/page_number/filename`) matching the real `SearchResult` (per `app/api/search.py` mapping). `PackageDocument` columns written (package_id/document_id/relevance_score/relevance_reason/excerpt/page_ranges) all exist (Phase 6A). `DocumentLinkResult` keys match `link_all` return.
- **Async/relationship safety:** linked documents are fetched with an explicit join (no lazy relationship load) and built into `LinkedDocumentResponse` — avoiding the `MissingGreenlet` class of bug seen in 8A detail.
