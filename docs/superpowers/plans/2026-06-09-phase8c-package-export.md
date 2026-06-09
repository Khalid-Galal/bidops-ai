# Phase 8C — Package Folders + Register + Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the on-disk package deliverables: a per-package folder tree (BOQ / Documents / Offers / Clarifications), a per-package BOQ-subset Excel, copied linked documents + a manifest, a Package Brief (HTML always; PDF when WeasyPrint is usable), and a master `Packages Register.xlsx` — with an export + register-download API.

**Architecture:** A `PackageExporter` (configurable `output_root`, default `data/packages`) walks a project's packages: for each it creates the folder tree, writes the BOQ subset via openpyxl, copies each linked document's real file (`Document.file_path`) into `Documents/` (graceful if the file is missing) plus a `linked_manifest.txt`, and writes a Brief — `Package_Brief.html` always (deterministic, testable), and `Package_Brief.pdf` additionally when WeasyPrint + native libs load (graceful skip otherwise, matching the existing PDF-export degradation). It records `folder_path`/`brief_path` on each `Package`, then writes the master `Packages Register.xlsx`. API: `POST /packages/export` (run it) and `GET /packages/register` (download the xlsx).

**Tech Stack:** Python 3.11, openpyxl, shutil/pathlib (stdlib), WeasyPrint (optional, graceful), FastAPI, httpx (ASGI tests), pytest.

**Reference:** `bidops-ai/backend/app/services/packaging_service.py` (`create_package_folder`, `generate_package_brief`). Adapt to openpyxl + HTML/WeasyPrint (root app uses WeasyPrint, not reportlab) + root models.

**Decomposition note:** Plan **8C** — final slice of Phase 8 (after 8A generation, 8B doc-linking). Consumes 6A (`Package`/`PackageDocument`/`BOQItem`/`Document`), 8A/8B output. Completes plan.md capabilities 4 + 6 (packaging + local folder structure).

---

## File Structure

- `app/services/packaging/package_exporter.py` — CREATE: `PackageExporter` (folders, BOQ subset, doc copy + manifest, brief HTML/PDF, register).
- `app/schemas/packaging.py` — MODIFY: add `PackageExportResult`.
- `app/api/packaging.py` — MODIFY: add `POST /export` + `GET /register`.
- `app/main.py` — no change (router already registered in 8A).
- `tests/packaging/test_package_exporter.py` — CREATE.
- `tests/packaging/test_packaging_api.py` — MODIFY: add export + register-download API test.
- `.gitignore` — verify `data/packages/` is ignored (covered by `data/`).

---

## Task 1: `PackageExporter` (folders + BOQ subset + docs + brief + register)

**Files:** Create `app/services/packaging/package_exporter.py`; Test `tests/packaging/test_package_exporter.py`

- [ ] **Step 1: Write the failing test `tests/packaging/test_package_exporter.py`**

```python
from pathlib import Path

from openpyxl import load_workbook


async def _seed(db, tmp_path):
    """Project + package + 2 BOQ items + a real doc file linked to the package."""
    from app.models.project import Project
    from app.models.document import Document
    from app.models.package import Package, PackageDocument
    from app.models.boq import BOQItem

    project = Project(name="New Cairo Medical Center")
    db.add(project)
    await db.flush()

    # a real file on disk for the linked document
    src = tmp_path / "concrete_spec.pdf"
    src.write_bytes(b"%PDF-1.4 fake spec content")
    doc = Document(
        project_id=project.id, filename="concrete_spec.pdf",
        file_path=str(src), file_type=".pdf", file_size=src.stat().st_size,
    )
    db.add(doc)
    await db.flush()

    pkg = Package(project_id=project.id, name="Concrete Works",
                  code="PKG-P0001-CON-001", trade_category="concrete", total_items=2)
    db.add(pkg)
    await db.flush()
    db.add_all([
        BOQItem(project_id=project.id, package_id=pkg.id, line_number="2.1",
                description="Reinforced concrete C35/45", unit="m3", quantity=5400,
                client_row_index=1, trade_category="concrete"),
        BOQItem(project_id=project.id, package_id=pkg.id, line_number="2.2",
                description="Reinforcement steel B500B", unit="ton", quantity=4900,
                client_row_index=2, trade_category="concrete"),
        BOQItem(project_id=project.id, package_id=None, line_number="9.9",
                description="Unassigned item", unit="no", quantity=1,
                client_row_index=3, trade_category=None),
    ])
    db.add(PackageDocument(package_id=pkg.id, document_id=doc.id,
                           relevance_score=0.9, relevance_reason="match",
                           excerpt="Concrete grade C35/45"))
    await db.commit()
    return project.id, pkg.id


async def test_export_creates_folders_boq_subset_docs_brief_register(db_session, tmp_path):
    from app.services.packaging.package_exporter import PackageExporter

    out = tmp_path / "packages_out"
    pid, pkg_id = await _seed(db_session, tmp_path)

    result = await PackageExporter(output_root=out).export_project(db_session, pid)

    assert result["packages_exported"] == 1
    pkg_dir = Path(result["packages"][0]["folder_path"])
    assert pkg_dir.is_dir()
    # folder tree
    for sub in ("BOQ", "Documents", "Offers", "Clarifications"):
        assert (pkg_dir / sub).is_dir()
    # BOQ subset xlsx with the 2 package items (not the unassigned one)
    boq_files = list((pkg_dir / "BOQ").glob("*.xlsx"))
    assert boq_files, "BOQ subset xlsx missing"
    wb = load_workbook(boq_files[0])
    ws = wb.active
    data_rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]]
    assert len(data_rows) == 2
    # linked document copied + manifest written
    assert (pkg_dir / "Documents" / "concrete_spec.pdf").exists()
    assert (pkg_dir / "Documents" / "linked_manifest.txt").exists()
    # brief HTML always written
    assert (pkg_dir / "Package_Brief.html").exists()
    brief_html = (pkg_dir / "Package_Brief.html").read_text(encoding="utf-8")
    assert "Concrete Works" in brief_html and "C35/45" in brief_html
    # master register at project root
    register = Path(result["register_path"])
    assert register.exists()
    rwb = load_workbook(register)
    rws = rwb.active
    reg_rows = [r for r in rws.iter_rows(min_row=2, values_only=True) if r and r[0]]
    assert any("PKG-P0001-CON-001" in str(r) for r in reg_rows)
    # package paths persisted
    from app.models.package import Package
    refreshed = await db_session.get(Package, pkg_id)
    assert refreshed.folder_path == str(pkg_dir)


async def test_export_missing_linked_file_is_graceful(db_session, tmp_path):
    from app.models.project import Project
    from app.models.document import Document
    from app.models.package import Package, PackageDocument
    from app.services.packaging.package_exporter import PackageExporter

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()
    doc = Document(project_id=project.id, filename="gone.pdf",
                   file_path=str(tmp_path / "does_not_exist.pdf"),
                   file_type=".pdf", file_size=0)
    db_session.add(doc)
    await db_session.flush()
    pkg = Package(project_id=project.id, name="MEP", code="PKG-P-MEP-001",
                  trade_category="mep", total_items=0)
    db_session.add(pkg)
    await db_session.flush()
    db_session.add(PackageDocument(package_id=pkg.id, document_id=doc.id))
    await db_session.commit()

    result = await PackageExporter(output_root=tmp_path / "o").export_project(db_session, project.id)
    # must not raise; the missing file is noted in the manifest, brief still written
    assert result["packages_exported"] == 1
    pkg_dir = Path(result["packages"][0]["folder_path"])
    assert not (pkg_dir / "Documents" / "gone.pdf").exists()
    manifest = (pkg_dir / "Documents" / "linked_manifest.txt").read_text(encoding="utf-8")
    assert "gone.pdf" in manifest and "MISSING" in manifest.upper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_package_exporter.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create `app/services/packaging/package_exporter.py`**

```python
"""Generates on-disk package deliverables: folders, BOQ subsets, linked docs,
briefs (HTML always, PDF when WeasyPrint is usable), and a master register."""

from __future__ import annotations

import html
import logging
import re
import shutil
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.document import Document
from app.models.package import Package, PackageDocument

logger = logging.getLogger(__name__)

_SUBFOLDERS = ("BOQ", "Documents", "Offers", "Clarifications")


def _safe_name(name: str) -> str:
    """Filesystem-safe folder/file component."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "package"


class PackageExporter:
    """Writes package folder trees + BOQ subsets + briefs + a master register."""

    def __init__(self, output_root: Path | str = "data/packages") -> None:
        self._root = Path(output_root)

    async def export_project(self, db: AsyncSession, project_id: int) -> dict:
        packages = (
            await db.execute(
                select(Package).where(Package.project_id == project_id).order_by(Package.code)
            )
        ).scalars().all()

        project_dir = self._root / f"project_{project_id}"
        project_dir.mkdir(parents=True, exist_ok=True)

        exported: list[dict] = []
        briefs_pdf = 0
        for pkg in packages:
            info = await self._export_package(db, pkg, project_dir)
            exported.append(info)
            if info["brief_pdf"]:
                briefs_pdf += 1

        register_path = self._write_register(project_dir, packages)
        await db.commit()  # persist folder_path/brief_path set on packages

        return {
            "project_id": project_id,
            "packages_exported": len(packages),
            "register_path": str(register_path),
            "briefs_pdf": briefs_pdf,
            "packages": exported,
        }

    async def _export_package(
        self, db: AsyncSession, pkg: Package, project_dir: Path
    ) -> dict:
        pkg_dir = project_dir / _safe_name(pkg.code)
        for sub in _SUBFOLDERS:
            (pkg_dir / sub).mkdir(parents=True, exist_ok=True)

        items = (
            await db.execute(
                select(BOQItem)
                .where(BOQItem.package_id == pkg.id)
                .order_by(BOQItem.client_row_index)
            )
        ).scalars().all()

        self._write_boq_subset(pkg_dir / "BOQ" / f"BOQ_{_safe_name(pkg.code)}.xlsx", pkg, items)

        links = (
            await db.execute(
                select(PackageDocument, Document)
                .join(Document, Document.id == PackageDocument.document_id)
                .where(PackageDocument.package_id == pkg.id)
                .order_by(PackageDocument.relevance_score.desc())
            )
        ).all()
        self._attach_documents(pkg_dir / "Documents", links)

        brief_html = pkg_dir / "Package_Brief.html"
        self._write_brief_html(brief_html, pkg, items, links)
        brief_pdf = self._try_write_brief_pdf(brief_html, pkg_dir / "Package_Brief.pdf")

        pkg.folder_path = str(pkg_dir)
        pkg.brief_path = str(brief_pdf or brief_html)
        return {
            "package_id": pkg.id,
            "code": pkg.code,
            "folder_path": str(pkg_dir),
            "brief_pdf": bool(brief_pdf),
            "documents_linked": len(links),
        }

    def _write_boq_subset(self, path: Path, pkg: Package, items: list[BOQItem]) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "BOQ"
        ws.append([f"Package: {pkg.code} - {pkg.name}"])
        ws["A1"].font = Font(bold=True, size=14)
        headers = ["Line", "Section", "Description", "Unit", "Quantity"]
        ws.append(headers)
        for cell in ws[2]:
            cell.font = Font(bold=True)
        for it in items:
            ws.append([it.line_number, it.section, it.description, it.unit, it.quantity])
        for col, width in {"A": 10, "B": 24, "C": 60, "D": 10, "E": 14}.items():
            ws.column_dimensions[col].width = width
        wb.save(path)

    def _attach_documents(self, docs_dir: Path, links: list) -> None:
        lines = ["Linked documents for this package", "=" * 40, ""]
        for pd, doc in links:
            src = Path(doc.file_path)
            status = "COPIED"
            if src.exists():
                try:
                    shutil.copy2(src, docs_dir / _safe_name(doc.filename))
                except OSError as exc:  # pragma: no cover
                    status = f"COPY_FAILED ({exc})"
            else:
                status = "MISSING (source file not found)"
            score = f"{pd.relevance_score:.2f}" if pd.relevance_score is not None else "n/a"
            lines.append(f"- {doc.filename} [{status}] relevance={score}")
            if pd.excerpt:
                lines.append(f"    excerpt: {pd.excerpt}")
        (docs_dir / "linked_manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_brief_html(
        self, path: Path, pkg: Package, items: list[BOQItem], links: list
    ) -> None:
        def esc(v) -> str:
            return html.escape(str(v if v is not None else ""))

        rows = "".join(
            f"<tr><td>{esc(i.line_number)}</td><td>{esc(i.description)}</td>"
            f"<td>{esc(i.unit)}</td><td>{esc(i.quantity)}</td></tr>"
            for i in items
        )
        doc_rows = "".join(
            f"<li>{esc(doc.filename)} (relevance "
            f"{esc(f'{pd.relevance_score:.2f}' if pd.relevance_score is not None else 'n/a')})</li>"
            for pd, doc in links
        )
        document = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Package Brief - {esc(pkg.code)}</title>
<style>body{{font-family:sans-serif;margin:2em}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #999;padding:4px;text-align:left}}h1{{font-size:1.4em}}</style></head>
<body>
<h1>Package Brief: {esc(pkg.name)}</h1>
<p><strong>Code:</strong> {esc(pkg.code)} &nbsp; <strong>Trade:</strong> {esc(pkg.trade_category)}
 &nbsp; <strong>Items:</strong> {esc(pkg.total_items)} &nbsp; <strong>Status:</strong> {esc(pkg.status)}</p>
<h2>Bill of Quantities</h2>
<table><tr><th>Line</th><th>Description</th><th>Unit</th><th>Qty</th></tr>{rows}</table>
<h2>Linked Documents</h2>
<ul>{doc_rows or '<li>None linked</li>'}</ul>
</body></html>"""
        path.write_text(document, encoding="utf-8")

    def _try_write_brief_pdf(self, html_path: Path, pdf_path: Path) -> Path | None:
        """Render the brief HTML to PDF if WeasyPrint + native libs are usable."""
        try:
            import weasyprint

            weasyprint.HTML(string=html_path.read_text(encoding="utf-8")).write_pdf(
                str(pdf_path)
            )
            return pdf_path
        except (ImportError, OSError) as exc:
            logger.info("Package brief PDF skipped (WeasyPrint unavailable): %s", exc)
            return None

    def _write_register(self, project_dir: Path, packages: list[Package]) -> Path:
        wb = Workbook()
        ws = wb.active
        ws.title = "Packages Register"
        headers = ["Code", "Name", "Trade", "Items", "Status", "Folder", "Brief"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for pkg in packages:
            ws.append([
                pkg.code, pkg.name, pkg.trade_category, pkg.total_items,
                pkg.status, pkg.folder_path or "", pkg.brief_path or "",
            ])
        for col, width in {"A": 22, "B": 28, "C": 16, "D": 8, "E": 12, "F": 40, "G": 40}.items():
            ws.column_dimensions[col].width = width
        path = project_dir / "Packages_Register.xlsx"
        wb.save(path)
        return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_package_exporter.py -v`
Expected: PASS (2 passed). (PDF brief is skipped gracefully on this host; HTML brief + register + folders are asserted.)

- [ ] **Step 5: Commit**

```bash
git add app/services/packaging/package_exporter.py tests/packaging/test_package_exporter.py
git commit -m "feat(packaging): PackageExporter — folders, BOQ subset, linked docs, brief, register"
```

---

## Task 2: API — export + register download

**Files:** Modify `app/schemas/packaging.py`, `app/api/packaging.py`; Test add to `tests/packaging/test_packaging_api.py`

- [ ] **Step 1: Add the failing API test to `tests/packaging/test_packaging_api.py`**

```python
async def test_export_and_register_download(pkg_client, monkeypatch, tmp_path):
    import app.api.packaging as pkg_api
    from app.services.packaging.package_exporter import PackageExporter

    client, pid = pkg_client

    # Force the exporter to write under a temp root (not data/packages).
    monkeypatch.setattr(
        pkg_api, "PackageExporter",
        lambda: PackageExporter(output_root=tmp_path / "pkgout"),
    )

    async with client:
        await client.post(f"/api/projects/{pid}/packages/generate")
        exp = await client.post(f"/api/projects/{pid}/packages/export")
        assert exp.status_code == 200, exp.text
        assert exp.json()["packages_exported"] == 2

        reg = await client.get(f"/api/projects/{pid}/packages/register")
        assert reg.status_code == 200
        assert reg.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(reg.content) > 0


async def test_register_download_404_before_export(pkg_client, monkeypatch, tmp_path):
    import app.api.packaging as pkg_api
    from app.services.packaging.package_exporter import PackageExporter

    client, pid = pkg_client
    monkeypatch.setattr(
        pkg_api, "PackageExporter",
        lambda: PackageExporter(output_root=tmp_path / "empty"),
    )
    async with client:
        r = await client.get(f"/api/projects/{pid}/packages/register")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py::test_export_and_register_download -v`
Expected: FAIL (no `/export` or `/register` route).

- [ ] **Step 3: Add `PackageExportResult` to `app/schemas/packaging.py`**

```python
class PackageExportResult(BaseModel):
    project_id: int
    packages_exported: int
    register_path: str
    briefs_pdf: int
```

- [ ] **Step 4: Extend `app/api/packaging.py`**

Add imports (module-level so the test can monkeypatch `PackageExporter`):
```python
from pathlib import Path
from fastapi.responses import FileResponse
from app.services.packaging.package_exporter import PackageExporter
from app.schemas.packaging import PackageExportResult
```

Add endpoints:
```python
@router.post("/export", response_model=PackageExportResult)
async def export_packages(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> PackageExportResult:
    """Generate folder structure, BOQ subsets, briefs, and the register on disk."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    summary = await PackageExporter().export_project(db, project_id)
    return PackageExportResult(
        project_id=summary["project_id"],
        packages_exported=summary["packages_exported"],
        register_path=summary["register_path"],
        briefs_pdf=summary["briefs_pdf"],
    )


@router.get("/register")
async def download_register(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download the master Packages Register.xlsx (run export first)."""
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    register = Path(PackageExporter()._root) / f"project_{project_id}" / "Packages_Register.xlsx"
    if not register.exists():
        raise HTTPException(
            status_code=404,
            detail="Register not found — run POST /packages/export first.",
        )
    return FileResponse(
        str(register),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Packages_Register_project_{project_id}.xlsx",
    )
```

Note: `/register` is a fixed segment; ensure it is declared BEFORE the `GET /{package_id}` route so it is not captured as a package id (it is a string, and `{package_id}` is `int`-typed, so FastAPI won't coerce "register" to int — but declare it before to be safe and explicit). The monkeypatched `PackageExporter()` in the test makes `_root` point at the temp dir so both endpoints agree on the path.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/packaging/test_packaging_api.py -v`
Expected: PASS (all packaging API tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/packaging.py app/api/packaging.py tests/packaging/test_packaging_api.py
git commit -m "feat(packaging): POST /packages/export + GET /packages/register download"
```

---

## Task 3: Full-suite check + gitignore

- [ ] **Step 1: Confirm package output is gitignored**

Run: `git check-ignore data/packages/x` → expect it printed (covered by `data/`). If not, add `data/packages/` to `.gitignore`.

- [ ] **Step 2: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (… + 8C). Report the count.

- [ ] **Step 3: Boot smoke**

Run: `.venv/Scripts/python.exe -c "import app.main; print('export/register:', [r.path for r in app.main.app.routes if r.path.endswith(('/export','/register'))])"`
Expected: shows the export + register routes.

---

## Self-Review (completed by author)

- **Spec coverage:** Completes plan.md capabilities 4+6: per-package folder tree (BOQ/Documents/Offers/Clarifications), per-package BOQ-subset Excel, copied linked documents + manifest, Package Brief (HTML always; PDF when WeasyPrint usable), master `Packages Register.xlsx`, with export + download API. `folder_path`/`brief_path` persisted on `Package`.
- **Graceful degradation:** missing source files → manifest notes `MISSING`, no crash (tested); WeasyPrint/Pango absent → PDF skipped, HTML brief still written (matches the existing PDF-export degradation and is the reason the brief is HTML-first).
- **Out of scope:** specs-vs-drawings folder split (needs doc classification — Phase 7C); supplier RFQ distribution (Phase 9).
- **Placeholder scan:** Complete code for the exporter, schema, API, and tests. No TODOs.
- **Type consistency:** `PackageExporter(output_root=...)` + `export_project(db, project_id)` consistent across service, API, tests. Reads `Document.file_path`/`filename` (exist, non-null) and writes `Package.folder_path`/`brief_path` (exist, nullable — Phase 6A). `PackageExportResult` keys match the summary subset returned by the endpoint. Linked docs fetched via explicit join (no lazy-load / MissingGreenlet).
- **Test isolation:** exporter tests use `db_session` + `tmp_path` output root; API tests monkeypatch `PackageExporter` to a `tmp_path` root so the real `data/packages` is never written; `get_db` overridden. `/register` 404 path tested before export.
