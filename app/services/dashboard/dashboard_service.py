"""Aggregated project status for the dashboard. Explicit queries only —
no relationship lazy-loads (MissingGreenlet), no LLM."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.document import Document
from app.models.email import EmailLog
from app.models.historical import HistoricalPrice
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.services.pricing.pricing_service import PricingService


class DashboardService:
    async def project_dashboard(self, db: AsyncSession, project_id: int) -> dict:
        project = await db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        docs_by_status = dict(
            (
                await db.execute(
                    select(Document.status, func.count())
                    .where(Document.project_id == project_id)
                    .group_by(Document.status)
                )
            ).all()
        )

        boq_total = (
            await db.execute(
                select(func.count(BOQItem.id)).where(BOQItem.project_id == project_id)
            )
        ).scalar() or 0
        boq_priced = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id,
                    BOQItem.unit_rate.is_not(None),
                    BOQItem.is_excluded.is_(False),
                )
            )
        ).scalar() or 0
        boq_excluded = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id, BOQItem.is_excluded.is_(True)
                )
            )
        ).scalar() or 0
        boq_classified = (
            await db.execute(
                select(func.count(BOQItem.id)).where(
                    BOQItem.project_id == project_id,
                    BOQItem.trade_category.is_not(None),
                )
            )
        ).scalar() or 0

        packages = list(
            (
                await db.execute(
                    select(Package)
                    .where(Package.project_id == project_id)
                    .order_by(Package.code)
                )
            ).scalars().all()
        )
        package_ids = [p.id for p in packages]
        package_status_counts = dict(Counter(p.status for p in packages))

        offers_by_status: dict[str, int] = {}
        emails_by_status: dict[str, int] = {}
        emails_by_type: dict[str, int] = {}
        if package_ids:
            offers_by_status = dict(
                (
                    await db.execute(
                        select(SupplierOffer.status, func.count())
                        .where(SupplierOffer.package_id.in_(package_ids))
                        .group_by(SupplierOffer.status)
                    )
                ).all()
            )
            emails_by_status = dict(
                (
                    await db.execute(
                        select(EmailLog.status, func.count())
                        .where(EmailLog.package_id.in_(package_ids))
                        .group_by(EmailLog.status)
                    )
                ).all()
            )
            emails_by_type = dict(
                (
                    await db.execute(
                        select(EmailLog.email_type, func.count())
                        .where(EmailLog.package_id.in_(package_ids))
                        .group_by(EmailLog.email_type)
                    )
                ).all()
            )

        suppliers_total = (
            await db.execute(select(func.count(Supplier.id)))
        ).scalar() or 0
        suppliers_active = (
            await db.execute(
                select(func.count(Supplier.id)).where(Supplier.is_active.is_(True))
            )
        ).scalar() or 0

        pricing_svc = PricingService()
        pricing = await pricing_svc.pricing_summary(db, project_id)
        gaps = await pricing_svc.gaps_report(db, project_id)

        historical_count = (
            await db.execute(select(func.count(HistoricalPrice.id)))
        ).scalar() or 0

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "extraction_status": project.extraction_status,
                "checklist_status": project.checklist_status,
            },
            "documents": {
                "total": sum(docs_by_status.values()),
                "by_status": docs_by_status,
            },
            "boq": {
                "total": boq_total,
                "classified": boq_classified,
                "priced": boq_priced,
                "unpriced": boq_total - boq_priced - boq_excluded,
                "excluded": boq_excluded,
            },
            "packages": [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "trade_category": p.trade_category,
                    "status": p.status,
                    "total_items": p.total_items or 0,
                    "offers_received": p.offers_received or 0,
                    "offers_evaluated": p.offers_evaluated or 0,
                }
                for p in packages
            ],
            "package_status_counts": package_status_counts,
            "suppliers": {"total": suppliers_total, "active": suppliers_active},
            "offers": {
                "total": sum(offers_by_status.values()),
                "by_status": offers_by_status,
            },
            "emails": {
                "total": sum(emails_by_status.values()),
                "by_status": emails_by_status,
                "by_type": emails_by_type,
            },
            "pricing": {
                "cost_subtotal": pricing["cost_subtotal"],
                "grand_total": pricing["grand_total"],
                "currency": pricing["currency"],
                "completion_rate": pricing["completion_rate"],
                "priced_items": pricing["priced_items"],
                "unpriced_items": pricing["unpriced_items"],
            },
            "gaps": {
                "unpriced": gaps["unpriced_count"],
                "needs_review": gaps["needs_review_count"],
                "excluded": gaps["excluded_count"],
            },
            "historical": {"corpus_records": historical_count},
        }
