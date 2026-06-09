"""RFQ email orchestration: build draft EmailLogs per package×supplier, list/
edit drafts, and send (explicit, separate step) via an injectable SMTPSender.

Draft-only by design: create_rfq_drafts NEVER sends. Nothing is auto-sent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EmailStatus, EmailType
from app.models.email import EmailLog
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier
from app.services.email.smtp_sender import SendError, SMTPSender
from app.services.email.templates import html_to_text, render_body
from app.services.rules.rules_service import RulesService

logger = logging.getLogger(__name__)

# Draft fields that may be edited before sending.
_EDITABLE = ("subject", "body_html", "to", "cc", "bcc", "reply_to")


class RFQService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    async def suggested_suppliers(
        self, db: AsyncSession, package_id: int
    ) -> list[Supplier]:
        package = await db.get(Package, package_id)
        if package is None:
            return []
        from app.services.supplier.supplier_service import SupplierService

        return await SupplierService().suppliers_for_trade(db, package.trade_category)

    def _from_address(self, rules) -> str:
        from app.config import get_settings

        s = get_settings()
        return rules.email.from_address or s.email_from or s.smtp_user or ""

    def _collect_attachments(
        self, package: Package, limit_mb: int
    ) -> tuple[list[dict], int, list[str]]:
        limit_bytes = max(limit_mb, 0) * 1024 * 1024
        candidates: list[Path] = []
        if package.brief_path:
            candidates.append(Path(package.brief_path))
        if package.folder_path:
            docs_dir = Path(package.folder_path) / "Documents"
            if docs_dir.is_dir():
                candidates += sorted(p for p in docs_dir.iterdir() if p.is_file())
        items: list[dict] = []
        total = 0
        skipped: list[str] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen or not path.exists():
                continue
            seen.add(key)
            size = path.stat().st_size
            if limit_bytes and total + size > limit_bytes:
                skipped.append(path.name)
                continue
            items.append({"name": path.name, "path": key, "size": size})
            total += size
        return items, total, skipped

    async def create_rfq_drafts(
        self,
        db: AsyncSession,
        package_id: int,
        supplier_ids: list[int],
        *,
        language: str | None = None,
        custom_message: str | None = None,
    ) -> list[EmailLog]:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        project = await db.get(Project, package.project_id)
        rules = self._rules()
        from_address = self._from_address(rules)
        reply_to = rules.email.reply_to or None
        attachments, total_size, _skipped = self._collect_attachments(
            package, rules.email.attachment_size_limit_mb
        )
        project_name = project.name if project else "Project"
        subject_fmt = rules.email.subject_formats.rfq

        drafts: list[EmailLog] = []
        # Dedupe supplier ids, preserving the caller's order, so a repeated id
        # never yields duplicate drafts.
        for supplier_id in dict.fromkeys(supplier_ids):
            supplier = await db.get(Supplier, supplier_id)
            if supplier is None or not supplier.emails:
                logger.info("Skipping supplier %s: missing or no email", supplier_id)
                continue
            lang = (
                language
                or supplier.preferred_language
                or rules.email.default_language
                or "en"
            )
            context = {
                "contact_name": supplier.contact_name or supplier.name,
                "project_name": project_name,
                "package_name": package.name,
                "package_code": package.code,
                "trade_category": (package.trade_category or "").replace("_", " ").title(),
                "scope_description": package.description or "Please refer to attached documents.",
                "deadline": (
                    package.submission_deadline.strftime("%Y-%m-%d")
                    if package.submission_deadline
                    else "To be confirmed"
                ),
                "submission_instructions": (
                    package.submission_instructions or "Please submit your quotation via email."
                ),
                "attachments": attachments,
                "custom_message": custom_message,
                "sender_name": get_settings_name(),
                "company_name": company_name(),
            }
            body_html = render_body("rfq", lang, context)
            subject = _safe_format(
                subject_fmt,
                project_code=project_name,
                package_name=package.name,
                package_code=package.code,
                supplier_name=supplier.name,
            )
            email_log = EmailLog(
                package_id=package.id,
                supplier_id=supplier.id,
                email_type=EmailType.RFQ.value,
                status=EmailStatus.DRAFT.value,
                to=list(supplier.emails),
                subject=subject,
                body_html=body_html,
                body_text=html_to_text(body_html),
                attachments=attachments or None,
                total_attachment_size=total_size or None,
                from_address=from_address or None,
                reply_to=reply_to,
            )
            db.add(email_log)
            drafts.append(email_log)

        await db.commit()
        for d in drafts:
            await db.refresh(d)
        return drafts

    async def get_email(self, db: AsyncSession, email_id: int) -> EmailLog | None:
        return await db.get(EmailLog, email_id)

    async def list_emails(
        self,
        db: AsyncSession,
        *,
        package_id: int | None = None,
        supplier_id: int | None = None,
        email_type: str | None = None,
        status: str | None = None,
    ) -> list[EmailLog]:
        stmt = select(EmailLog)
        if package_id is not None:
            stmt = stmt.where(EmailLog.package_id == package_id)
        if supplier_id is not None:
            stmt = stmt.where(EmailLog.supplier_id == supplier_id)
        if email_type is not None:
            stmt = stmt.where(EmailLog.email_type == email_type)
        if status is not None:
            stmt = stmt.where(EmailLog.status == status)
        stmt = stmt.order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
        return list((await db.execute(stmt)).scalars().all())

    async def update_draft(
        self, db: AsyncSession, email_id: int, **fields
    ) -> EmailLog | None:
        email_log = await db.get(EmailLog, email_id)
        if email_log is None:
            return None
        if email_log.status != EmailStatus.DRAFT.value:
            raise ValueError("Only DRAFT emails can be edited")
        for key, value in fields.items():
            if value is None or key not in _EDITABLE:
                continue
            setattr(email_log, key, value)
        if "body_html" in fields and fields["body_html"]:
            email_log.body_text = html_to_text(fields["body_html"])
        await db.commit()
        await db.refresh(email_log)
        return email_log

    async def send(
        self,
        db: AsyncSession,
        email_id: int,
        *,
        sender: SMTPSender | None = None,
    ) -> EmailLog:
        email_log = await db.get(EmailLog, email_id)
        if email_log is None:
            raise ValueError(f"Email {email_id} not found")
        if email_log.status == EmailStatus.SENT.value:
            return email_log
        sender = sender or SMTPSender()
        if not sender.is_configured():
            raise RuntimeError(
                "SMTP is not configured. Set BIDOPS_SMTP_HOST/USER/PASSWORD in .env."
            )
        try:
            message_id = sender.send(
                from_address=email_log.from_address or "",
                from_name=get_settings_name(),
                to=list(email_log.to or []),
                cc=email_log.cc,
                bcc=email_log.bcc,
                reply_to=email_log.reply_to,
                subject=email_log.subject,
                body_text=email_log.body_text,
                body_html=email_log.body_html,
                attachments=email_log.attachments,
            )
        except SendError as exc:
            # Log full diagnostics server-side, but never surface raw SMTP/
            # socket text (host/IP/auth details) to clients.
            logger.warning("SMTP send failed for email %s: %s", email_id, exc)
            email_log.status = EmailStatus.FAILED.value
            email_log.error_message = "SMTP send failed"
            email_log.retry_count += 1
            await db.commit()
            await db.refresh(email_log)
            return email_log

        email_log.status = EmailStatus.SENT.value
        email_log.sent_at = datetime.now(timezone.utc)
        email_log.message_id = message_id
        if email_log.supplier_id and email_log.email_type == EmailType.RFQ.value:
            supplier = await db.get(Supplier, email_log.supplier_id)
            if supplier is not None:
                supplier.total_rfqs_sent = (supplier.total_rfqs_sent or 0) + 1
        await db.commit()
        await db.refresh(email_log)
        return email_log


def _safe_format(template: str, **values) -> str:
    """Format ``template`` defensively for operator-editable subject formats.

    Never raises — a missing placeholder renders as ``{key}``; on any other
    malformed/invalid format string (bad spec, positional field, etc.) the raw
    template is returned unchanged.
    """

    class _Default(dict):
        def __missing__(self, key):  # noqa: D401
            return "{" + key + "}"

    try:
        return template.format_map(_Default(values))
    except (ValueError, IndexError, KeyError) as exc:
        logger.warning("Invalid subject format %r: %s", template, exc)
        return template


def get_settings_name() -> str:
    from app.config import get_settings

    return get_settings().email_from_name


def company_name() -> str:
    from app.config import get_settings

    return get_settings().company_name
