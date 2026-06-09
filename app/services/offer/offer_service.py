"""Offer lifecycle: create from files, manual commercial entry, list, select.

Pure DB/logic — no LLM. Works fully without a Gemini key.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.supplier import Supplier, SupplierOffer

_SETTABLE = (
    "total_price", "currency", "vat_included", "vat_amount", "validity_days",
    "payment_terms", "delivery_weeks", "delivery_terms", "technical_score",
    "exclusions", "deviations", "line_items", "evaluator_notes",
)


class OfferService:
    async def create_offer(
        self, db: AsyncSession, package_id: int, supplier_id: int, file_paths: list[str]
    ) -> SupplierOffer:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValueError(f"Supplier {supplier_id} not found")
        offer = SupplierOffer(
            package_id=package_id,
            supplier_id=supplier_id,
            file_paths=list(file_paths or []),
            status=OfferStatus.RECEIVED.value,
            received_at=datetime.now(timezone.utc),
        )
        db.add(offer)
        package.offers_received = (package.offers_received or 0) + 1
        supplier.total_offers_received = (supplier.total_offers_received or 0) + 1
        await db.commit()
        await db.refresh(offer)
        return offer

    async def get_offer(self, db: AsyncSession, offer_id: int) -> SupplierOffer | None:
        return await db.get(SupplierOffer, offer_id)

    async def list_offers(self, db: AsyncSession, package_id: int) -> list[SupplierOffer]:
        stmt = (
            select(SupplierOffer)
            .where(SupplierOffer.package_id == package_id)
            .order_by(SupplierOffer.overall_score.desc().nullslast(), SupplierOffer.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def update_commercial(
        self, db: AsyncSession, offer_id: int, **fields
    ) -> SupplierOffer | None:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            return None
        for key, value in fields.items():
            if value is not None and key in _SETTABLE:
                setattr(offer, key, value)
        await db.commit()
        await db.refresh(offer)
        return offer

    async def select_offer(
        self, db: AsyncSession, offer_id: int, notes: str | None = None
    ) -> SupplierOffer | None:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            return None
        was_selected = offer.status == OfferStatus.SELECTED.value
        # Decrement the award counter of every OTHER currently-selected offer's
        # supplier before they are demoted, so a winner switch is award-neutral
        # for the loser (and never leaves total_awards inflated).
        demoted = (
            await db.execute(
                select(SupplierOffer).where(
                    SupplierOffer.package_id == offer.package_id,
                    SupplierOffer.status == OfferStatus.SELECTED.value,
                    SupplierOffer.id != offer.id,
                )
            )
        ).scalars().all()
        for prev in demoted:
            prev_supplier = await db.get(Supplier, prev.supplier_id)
            if prev_supplier is not None:
                prev_supplier.total_awards = max(0, (prev_supplier.total_awards or 0) - 1)
        # Demote any previously-selected offer in this package back to evaluated.
        await db.execute(
            update(SupplierOffer)
            .where(
                SupplierOffer.package_id == offer.package_id,
                SupplierOffer.status == OfferStatus.SELECTED.value,
                SupplierOffer.id != offer.id,
            )
            .values(status=OfferStatus.EVALUATED.value)
        )
        offer.status = OfferStatus.SELECTED.value
        if notes is not None:
            offer.recommendation = notes
        # Only count a genuine transition into SELECTED; re-selecting the same
        # offer is idempotent for the award counter.
        if not was_selected:
            supplier = await db.get(Supplier, offer.supplier_id)
            if supplier is not None:
                supplier.total_awards = (supplier.total_awards or 0) + 1
        await db.commit()
        await db.refresh(offer)
        return offer
