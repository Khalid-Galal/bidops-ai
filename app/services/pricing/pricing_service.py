"""BOQ pricing: populate from offers, summarize with markups, report gaps.

Pure DB/logic — no LLM. Mapping uses the deterministic fuzzy matcher; an
optional semantic_scorer can be injected for a future embedding-based blend.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.supplier import SupplierOffer
from app.services.pricing.line_item_matcher import (
    DEFAULT_THRESHOLD,
    HIGH_CONFIDENCE,
    best_match,
)
from app.services.rules.rules_service import RulesService


class PricingService:
    def __init__(self, rules_service: RulesService | None = None, semantic_scorer=None) -> None:
        self._rules_service = rules_service or RulesService()
        self._semantic_scorer = semantic_scorer

    def _rules(self):
        return self._rules_service.load()

    def _markup_factor(self) -> float:
        m = self._rules().commercial.markup
        return 1.0 + (m.overhead + m.profit + m.contingency + m.risk)

    async def populate_from_offer(
        self,
        db: AsyncSession,
        offer_id: int,
        *,
        apply_markup: bool = False,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        if offer.status != OfferStatus.SELECTED.value:
            raise ValueError("Only a selected offer can price a package")
        line_items = offer.line_items or []
        if not line_items:
            raise ValueError("Offer has no line items to populate from")

        boq_items = list(
            (
                await db.execute(
                    select(BOQItem)
                    .where(BOQItem.package_id == offer.package_id)
                    .order_by(BOQItem.client_row_index, BOQItem.id)
                )
            ).scalars().all()
        )
        factor = self._markup_factor() if apply_markup else 1.0

        populated = needs_review = unmatched = 0
        total_value = 0.0
        for item in boq_items:
            match, score = best_match(
                item.description, line_items,
                threshold=threshold, semantic_scorer=self._semantic_scorer,
            )
            if match is None:
                item.requires_review = True
                item.review_notes = "No offer line item matched this BOQ item"
                unmatched += 1
                continue
            rate = float(match.get("rate") or match.get("unit_rate") or 0.0)
            if rate <= 0:
                item.requires_review = True
                item.review_notes = "Matched offer line item has no usable rate"
                unmatched += 1
                continue
            rate *= factor
            item.unit_rate = round(rate, 2)
            item.total_price = round(rate * item.quantity, 2)
            item.currency = offer.currency
            item.selected_offer_id = offer.id
            item.mapping_confidence = score
            item.requires_review = score < HIGH_CONFIDENCE
            if item.requires_review:
                item.review_notes = f"Low-confidence price mapping ({score})"
                needs_review += 1
            else:
                item.review_notes = None
            total_value += item.total_price
            populated += 1

        await db.commit()
        return {
            "offer_id": offer_id,
            "package_id": offer.package_id,
            "items_populated": populated,
            "items_needs_review": needs_review,
            "items_unmatched": unmatched,
            "total_value": round(total_value, 2),
            "currency": offer.currency,
            "markup_applied": apply_markup,
        }
