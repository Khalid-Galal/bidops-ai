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


async def test_analyze_does_not_supersede_unit_designators(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Villa Type V1 Drawings.pdf", text="villa one drawings")
    b = _doc(pid, "Villa Type V2 Drawings.pdf", text="villa two drawings")
    db_session.add_all([a, b])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.is_superseded is False
    assert b.is_superseded is False
    assert result["superseded"] == 0


async def test_analyze_skips_mixed_alpha_numeric_chain(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Spec Rev A.pdf", text="spec rev a")
    b = _doc(pid, "Spec Rev 1.pdf", text="spec rev 1")
    db_session.add_all([a, b])
    await db_session.commit()
    await VersioningService().analyze(db_session, pid)
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.is_superseded is False
    assert b.is_superseded is False


async def test_analyze_exempts_addendum_chain(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Addendum v1.pdf", text="addendum one to the tender")
    b = _doc(pid, "Addendum v2.pdf", text="addendum two to the tender")
    db_session.add_all([a, b])
    await db_session.commit()
    await VersioningService().analyze(db_session, pid)
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.category == "addendum"
    assert b.category == "addendum"
    assert a.is_superseded is False
    assert b.is_superseded is False


async def test_analyze_prunes_superseded_links(db_session):
    from app.models.package import Package, PackageDocument

    pid = await _seed_project(db_session)
    a = _doc(pid, "Spec_RevA.pdf", text="spec rev a")
    b = _doc(pid, "Spec_RevB.pdf", text="spec rev b")
    db_session.add_all([a, b])
    await db_session.flush()
    pkg = Package(project_id=pid, name="Specs", code="PKG-1",
                  trade_category="specs", total_items=0)
    db_session.add(pkg)
    await db_session.flush()
    # Link RevA (which will become superseded) to the package directly.
    db_session.add(PackageDocument(package_id=pkg.id, document_id=a.id))
    await db_session.commit()

    await VersioningService().analyze(db_session, pid)
    await db_session.refresh(a)
    assert a.is_superseded is True

    rows = (
        await db_session.execute(
            select(PackageDocument).where(PackageDocument.document_id == a.id)
        )
    ).scalars().all()
    assert rows == []  # superseded doc's link was pruned


async def test_duplicate_also_in_chain(db_session, tmp_path):
    # A revision pair whose files are BYTE-IDENTICAL: dedup runs first and keeps
    # the earliest copy, so exactly one document remains live.
    pid = await _seed_project(db_session)
    f1 = tmp_path / "a.pdf"; f1.write_bytes(b"IDENTICAL SPEC BYTES")
    f2 = tmp_path / "b.pdf"; f2.write_bytes(b"IDENTICAL SPEC BYTES")
    a = _doc(pid, "Spec_RevA.pdf", str(f1))
    b = _doc(pid, "Spec_RevB.pdf", str(f2))
    db_session.add_all([a, b])
    await db_session.commit()
    result = await VersioningService().analyze(db_session, pid)
    await db_session.refresh(a)
    await db_session.refresh(b)
    live = [d for d in (a, b) if not d.is_superseded]
    assert len(live) == 1
    # Dedup keeps the earliest (RevA); RevB is the duplicate. Chain does not
    # double-mark (RevB already in dedup set).
    assert a.is_superseded is False
    assert b.is_superseded is True
    assert b.supersede_reason.startswith("auto:duplicate")
    assert result["duplicates"] == 1
    assert result["superseded"] == 0


async def test_rank_zero_base_grouping(db_session):
    # Positive: an un-versioned base + an explicit Rev A (same base+type) form a
    # chain; the base (rank 0) is superseded, RevA (rank 1) is the keeper.
    pid = await _seed_project(db_session)
    base = _doc(pid, "Specifications.pdf", text="specification base")
    rev = _doc(pid, "Specifications Rev A.pdf", text="specification rev a")
    db_session.add_all([base, rev])
    await db_session.commit()
    await VersioningService().analyze(db_session, pid)
    await db_session.refresh(base)
    await db_session.refresh(rev)
    assert base.is_superseded is True
    assert rev.is_superseded is False
    assert base.superseded_by_id == rev.id

    # Negative: same base text but DIFFERENT file_type — not the same chain.
    pid2 = await _seed_project(db_session)
    p = _doc(pid2, "BOQ.pdf", text="boq pdf")
    x = _doc(pid2, "BOQ rev 2.xlsx", text="boq xlsx")
    db_session.add_all([p, x])
    await db_session.commit()
    await VersioningService().analyze(db_session, pid2)
    await db_session.refresh(p)
    await db_session.refresh(x)
    assert p.is_superseded is False
    assert x.is_superseded is False


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
    # unmark installs a durable pin sentinel so re-analysis never re-marks it.
    assert d.supersede_reason == "manual:keep"


async def test_undo_survives_reanalyze(db_session):
    pid = await _seed_project(db_session)
    a = _doc(pid, "Spec_RevA.pdf", text="spec rev a")
    b = _doc(pid, "Spec_RevB.pdf", text="spec rev b")
    db_session.add_all([a, b])
    await db_session.commit()
    svc = VersioningService()
    await svc.analyze(db_session, pid)
    await db_session.refresh(a)
    assert a.is_superseded is True  # auto-superseded by RevB
    # User undoes the auto mark — installs the durable pin.
    await svc.unmark_superseded(db_session, a.id)
    # Re-analyze: the pin must hold, RevA stays live.
    await svc.analyze(db_session, pid)
    await db_session.refresh(a)
    assert a.is_superseded is False
    assert a.supersede_reason == "manual:keep"
