import pytest
from sqlalchemy import select

from app.models.document import Document
from pathlib import Path

from app.models.project import Project
from app.services.versioning.versioning_service import VersioningService


async def test_document_versioning_columns_persist(db_session):
    doc = Document(
        project_id=1, filename="Spec_RevB.pdf", file_path="/t/s.pdf",
        file_type="pdf", file_size=1,
        category="specs", content_hash="ab" * 32,
        is_superseded=True, superseded_by_id=99,
        version_label="rev B", supersede_reason="auto:test",
    )
    db_session.add(doc)
    await db_session.commit()
    got = (await db_session.execute(select(Document))).scalar_one()
    assert got.category == "specs"
    assert got.is_superseded is True
    assert got.superseded_by_id == 99
    assert got.version_label == "rev B"
    assert got.supersede_reason == "auto:test"


async def _seed_project(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    return project.id


def _doc(pid, filename, path="/missing", text=None, **kw):
    return Document(project_id=pid, filename=filename, file_path=path,
                    file_type=Path(filename).suffix.lstrip(".") or "pdf",
                    file_size=1, extracted_text=text, **kw)


async def test_analyze_marks_duplicates_by_content(db_session, tmp_path):
    pid = await _seed_project(db_session)
    f1 = tmp_path / "a.pdf"; f1.write_bytes(b"SAME BYTES")
    f2 = tmp_path / "b.pdf"; f2.write_bytes(b"SAME BYTES")
    d1 = _doc(pid, "Original.pdf", str(f1))
    d2 = _doc(pid, "Copy of Original.pdf", str(f2))
    db_session.add_all([d1, d2])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    assert result["duplicates"] == 1
    await db_session.refresh(d2)
    assert d2.is_superseded is True
    assert d2.superseded_by_id == d1.id
    assert d2.supersede_reason.startswith("auto:duplicate")
    await db_session.refresh(d1)
    assert d1.is_superseded is False


async def test_analyze_marks_older_revisions(db_session):
    pid = await _seed_project(db_session)
    old = _doc(pid, "Spec_RevA.pdf", text="specification rev a")
    new = _doc(pid, "Spec_RevB.pdf", text="specification rev b")
    db_session.add_all([old, new])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    assert result["superseded"] == 1
    await db_session.refresh(old)
    await db_session.refresh(new)
    assert old.is_superseded is True
    assert old.superseded_by_id == new.id
    assert "newer revision" in old.supersede_reason
    assert new.is_superseded is False
    assert new.version_label == "rev B"


async def test_analyze_classifies_documents(db_session):
    pid = await _seed_project(db_session)
    d = _doc(pid, "Addendum_01.pdf", text="addendum to the tender")
    db_session.add(d)
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    await db_session.refresh(d)
    assert d.category == "addendum"
    assert result["by_category"]["addendum"] == 1


async def test_analyze_is_idempotent_and_preserves_manual_marks(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Spec_RevA.pdf", text="x")
    b = _doc(pid, "Spec_RevB.pdf", text="y")
    manual = _doc(pid, "Old base ITT.pdf", text="itt")
    db_session.add_all([a, b, manual])
    await db_session.commit()
    svc = VersioningService()
    await svc.analyze(db_session, pid)
    # manual mark with a human reason
    await svc.mark_superseded(db_session, manual.id, superseded_by_id=b.id,
                              reason="replaced by addendum 2 (manual)")
    # re-analyze: auto marks recomputed, manual mark must survive
    result2 = await svc.analyze(db_session, pid)
    await db_session.refresh(manual)
    assert manual.is_superseded is True
    assert manual.supersede_reason == "replaced by addendum 2 (manual)"
    await db_session.refresh(a)
    assert a.is_superseded is True  # auto mark re-applied
    assert result2["superseded"] == 1


async def test_unmark_superseded(db_session):
    pid = await _seed_project(db_session)
    d = _doc(pid, "Doc.pdf")
    db_session.add(d)
    await db_session.commit()
    svc = VersioningService()
    await svc.mark_superseded(db_session, d.id, superseded_by_id=None, reason="mistake")
    await db_session.refresh(d)
    assert d.is_superseded is True
    await svc.unmark_superseded(db_session, d.id)
    await db_session.refresh(d)
    assert d.is_superseded is False
    assert d.supersede_reason is None
