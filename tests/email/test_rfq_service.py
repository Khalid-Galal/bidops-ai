import pytest

from app.models.base import EmailStatus, EmailType
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier
from app.schemas.rules import RulesConfig
from app.services.email.rfq_service import RFQService
from app.services.email.smtp_sender import SendError


class _FakeRules:
    """Stands in for RulesService — returns a fixed RulesConfig from load()."""

    def __init__(self, cfg):
        self._cfg = cfg

    def load(self):
        return self._cfg


async def _seed(db):
    project = Project(name="Metro Line 3")
    db.add(project)
    await db.flush()
    package = Package(
        project_id=project.id, name="HVAC Works", code="PKG-001-MEP",
        trade_category="mep", description="Supply and install HVAC.",
    )
    db.add(package)
    sup_en = Supplier(name="CoolAir", emails=["sales@coolair.test"],
                      trade_categories=["mep"], preferred_language="en", contact_name="Sam")
    sup_ar = Supplier(name="HawaCo", emails=["bids@hawa.test"],
                      trade_categories=["mep"], preferred_language="ar")
    sup_none = Supplier(name="NoEmail", emails=[], trade_categories=["mep"])
    db.add_all([sup_en, sup_ar, sup_none])
    await db.commit()
    for obj in (package, sup_en, sup_ar, sup_none):
        await db.refresh(obj)
    return project, package, sup_en, sup_ar, sup_none


async def test_suggested_suppliers_matches_trade(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    suggestions = await RFQService().suggested_suppliers(db_session, package.id)
    names = {s.name for s in suggestions}
    assert {"CoolAir", "HawaCo", "NoEmail"} <= names


async def test_create_rfq_drafts_are_drafts_only(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id, sup_ar.id]
    )
    assert len(drafts) == 2
    for d in drafts:
        assert d.status == EmailStatus.DRAFT.value
        assert d.email_type == EmailType.RFQ.value
        assert d.sent_at is None
    # language honored: Arabic supplier draft is RTL
    ar_draft = next(d for d in drafts if d.supplier_id == sup_ar.id)
    assert 'dir="rtl"' in ar_draft.body_html
    en_draft = next(d for d in drafts if d.supplier_id == sup_en.id)
    assert "CoolAir" not in en_draft.body_html  # uses contact_name, not company
    assert "Sam" in en_draft.body_html
    assert en_draft.to == ["sales@coolair.test"]


async def test_create_rfq_skips_supplier_without_email(db_session):
    _, package, sup_en, sup_ar, sup_none = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(db_session, package.id, [sup_none.id])
    assert drafts == []


async def test_language_override(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id], language="ar"
    )
    assert 'dir="rtl"' in drafts[0].body_html


async def test_subject_uses_rules_format(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(db_session, package.id, [sup_en.id])
    # default rules.email.subject_formats.rfq = "[{project_code}] RFQ - {package_name}"
    assert drafts[0].subject == "[Metro Line 3] RFQ - HVAC Works"


async def test_list_get_and_update_draft(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    assert (await svc.get_email(db_session, draft.id)).id == draft.id
    listed = await svc.list_emails(db_session, package_id=package.id)
    assert len(listed) == 1
    updated = await svc.update_draft(db_session, draft.id, subject="Edited", to=["new@x.test"])
    assert updated.subject == "Edited"
    assert updated.to == ["new@x.test"]


async def test_update_draft_rejects_sent(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    draft.status = EmailStatus.SENT.value
    await db_session.commit()
    with pytest.raises(ValueError):
        await svc.update_draft(db_session, draft.id, subject="too late")


class _FakeSender:
    def __init__(self, configured=True, fail=False):
        self._configured = configured
        self._fail = fail
        self.calls = []

    def is_configured(self):
        return self._configured

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise SendError("smtp boom")
        return "<msgid@test>"


async def test_send_uses_injected_sender_and_marks_sent(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    sender = _FakeSender()
    out = await svc.send(db_session, draft.id, sender=sender)
    assert out.status == EmailStatus.SENT.value
    assert out.message_id == "<msgid@test>"
    assert out.sent_at is not None
    assert len(sender.calls) == 1
    assert sender.calls[0]["to"] == ["sales@coolair.test"]
    assert sender.calls[0]["subject"] == draft.subject
    assert sender.calls[0]["body_html"]
    # supplier RFQ counter incremented
    refreshed = await db_session.get(Supplier, sup_en.id)
    assert refreshed.total_rfqs_sent == 1


async def test_send_failure_marks_failed(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    out = await svc.send(db_session, draft.id, sender=_FakeSender(fail=True))
    assert out.status == EmailStatus.FAILED.value
    # Raw SMTP/socket text is never surfaced to clients; generic message only.
    assert out.error_message == "SMTP send failed"
    assert out.retry_count == 1


async def test_send_raises_when_not_configured(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    svc = RFQService()
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    with pytest.raises(RuntimeError):
        await svc.send(db_session, draft.id, sender=_FakeSender(configured=False))


async def test_misconfigured_subject_format_does_not_crash(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    cfg = RulesConfig()
    bad_template = "[{project_code}] #{seq:04d}"  # 'seq' is not provided -> KeyError
    cfg.email.subject_formats.rfq = bad_template
    svc = RFQService(rules_service=_FakeRules(cfg))
    drafts = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])
    assert len(drafts) == 1
    # Falls back to the raw template instead of crashing.
    assert drafts[0].subject == bad_template


async def test_duplicate_supplier_ids_create_one_draft(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id, sup_en.id]
    )
    assert len(drafts) == 1


async def test_custom_message_appears_in_draft(db_session):
    _, package, sup_en, *_ = await _seed(db_session)
    drafts = await RFQService().create_rfq_drafts(
        db_session, package.id, [sup_en.id], custom_message="Site visit Tuesday"
    )
    assert "Site visit Tuesday" in drafts[0].body_html
    assert "Site visit Tuesday" in drafts[0].body_text


async def test_attachments_collected_and_size_capped(db_session, tmp_path):
    _, package, sup_en, *_ = await _seed(db_session)
    # Real folder layout: <folder>/Documents/{brief.pdf, a.pdf, b.pdf}.
    folder = tmp_path / "PKG-001-MEP"
    docs = folder / "Documents"
    docs.mkdir(parents=True)
    brief = docs / "brief.pdf"        # lives INSIDE Documents -> must dedupe
    brief.write_bytes(b"x" * 1024)    # ~1 KB
    a = docs / "a.pdf"
    a.write_bytes(b"y" * (200 * 1024))      # ~200 KB, kept
    b = docs / "b.pdf"
    b.write_bytes(b"z" * (2 * 1024 * 1024))  # 2 MB, dropped by a 1 MB cap
    package.folder_path = str(folder)
    package.brief_path = str(brief)
    await db_session.commit()

    cfg = RulesConfig()
    cfg.email.attachment_size_limit_mb = 1  # 1 MiB cap -> b.pdf excluded
    svc = RFQService(rules_service=_FakeRules(cfg))
    [draft] = await svc.create_rfq_drafts(db_session, package.id, [sup_en.id])

    names = [att["name"] for att in draft.attachments]
    # brief appears exactly once despite being both brief_path and in Documents.
    assert names.count("brief.pdf") == 1
    assert "a.pdf" in names
    assert "b.pdf" not in names  # oversized -> dropped
    kept_sizes = {att["name"]: att["size"] for att in draft.attachments}
    assert kept_sizes["a.pdf"] == a.stat().st_size
    assert kept_sizes["brief.pdf"] == brief.stat().st_size
    assert draft.total_attachment_size == sum(kept_sizes.values())
