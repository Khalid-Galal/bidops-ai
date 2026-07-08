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
from app.services.pricing.commercial import compute_commercial
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

    @staticmethod
    def _clear_pricing(item: BOQItem) -> None:
        """Drop any stale price so a re-population that no longer matches an
        item leaves it cleanly unpriced rather than keeping the old value."""
        item.unit_rate = None
        item.total_price = None
        item.currency = None
        item.selected_offer_id = None
        item.mapping_confidence = None

    async def populate_from_offer(
        self,
        db: AsyncSession,
        offer_id: int,
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> dict:
        """Price a package's BOQ items from a SELECTED offer's line items.

        Note: the deterministic v1 fuzzy matcher may map MANY BOQ items to ONE
        offer line item, and the unit of measure is NOT cross-checked between
        the matched pair. Raw cost rates are stored here; the single
        cost->selling markup layer is applied later in ``pricing_summary``.
        """
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        if offer.status != OfferStatus.SELECTED.value:
            raise ValueError("Only a selected offer can price a package")
        line_items = offer.line_items or []
        if not line_items:
            raise ValueError("Offer has no line items to populate from")
        quantity_tolerance = self._rules().measurement.quantity_tolerance

        boq_items = list(
            (
                await db.execute(
                    select(BOQItem)
                    .where(BOQItem.package_id == offer.package_id)
                    .order_by(BOQItem.client_row_index, BOQItem.id)
                )
            ).scalars().all()
        )
        populated = needs_review = unmatched = 0
        total_value = 0.0
        for item in boq_items:
            if item.is_excluded:
                continue
            match, score = best_match(
                item.description, line_items,
                threshold=threshold, semantic_scorer=self._semantic_scorer,
            )
            if match is None:
                self._clear_pricing(item)
                item.requires_review = True
                item.review_notes = "No offer line item matched this BOQ item"
                unmatched += 1
                continue
            rate = float(match.get("rate") or match.get("unit_rate") or 0.0)
            if rate <= 0:
                self._clear_pricing(item)
                item.requires_review = True
                item.review_notes = "Matched offer line item has no usable rate"
                unmatched += 1
                continue
            item.unit_rate = round(rate, 2)
            item.total_price = round(rate * item.quantity, 2)
            item.currency = offer.currency
            item.selected_offer_id = offer.id
            item.mapping_confidence = score
            notes = []
            if score < HIGH_CONFIDENCE:
                notes.append(f"Low-confidence price mapping ({score})")
            match_qty = match.get("quantity")
            if match_qty not in (None, 0) and item.quantity:
                qty_diff = abs(item.quantity - match_qty) / abs(item.quantity)
                if qty_diff > quantity_tolerance:
                    notes.append(
                        f"Offer quantity {match_qty} differs from BOQ quantity "
                        f"{item.quantity} by more than {quantity_tolerance:.0%}"
                    )
            item.requires_review = bool(notes)
            item.review_notes = "; ".join(notes) or None
            if item.requires_review:
                needs_review += 1
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
        }

    async def pricing_summary(self, db: AsyncSession, project_id: int) -> dict:
        items = list(
            (
                await db.execute(select(BOQItem).where(BOQItem.project_id == project_id))
            ).scalars().all()
        )
        rules = self._rules()
        priced = [i for i in items if i.total_price is not None and not i.is_excluded]
        cost_subtotal = round(sum(i.total_price for i in priced), 2)

        commercial = compute_commercial(cost_subtotal, rules)

        by_trade: dict[str, dict] = {}
        for i in priced:
            trade = i.trade_category or "uncategorized"
            bucket = by_trade.setdefault(trade, {"count": 0, "total": 0.0})
            bucket["count"] += 1
            bucket["total"] += i.total_price
        by_trade_list = [
            {
                "trade": trade,
                "count": data["count"],
                "total": round(data["total"], 2),
                "percentage": round(data["total"] / cost_subtotal * 100, 1) if cost_subtotal else 0.0,
            }
            for trade, data in sorted(by_trade.items(), key=lambda kv: -kv[1]["total"])
        ]

        # The summary numbers are in the offer/cost currency (no FX conversion
        # is performed), so they must be LABELED with that currency. Prefer the
        # priced items' currency; fall back to the rules' commercial currency,
        # then a guaranteed non-null default so the field is never None.
        currency = next(
            (i.currency for i in priced if i.currency), None
        ) or rules.commercial.currency or "USD"
        return {
            "project_id": project_id,
            "currency": currency,
            "total_items": len(items),
            "priced_items": len(priced),
            "unpriced_items": len(items) - len(priced),
            "completion_rate": round(len(priced) / len(items) * 100, 1) if items else 0.0,
            "cost_subtotal": cost_subtotal,
            "markups": commercial["markups"],
            "selling_before_vat": commercial["selling_before_vat"],
            "vat_rate": commercial["vat_rate"],
            "vat_amount": commercial["vat_amount"],
            "grand_total": commercial["grand_total"],
            "by_trade": by_trade_list,
        }

    async def gaps_report(self, db: AsyncSession, project_id: int) -> dict:
        items = list(
            (
                await db.execute(select(BOQItem).where(BOQItem.project_id == project_id))
            ).scalars().all()
        )

        def gap(item, reason: str) -> dict:
            return {
                "id": item.id,
                "line_number": item.line_number,
                "description": item.description,
                "trade_category": item.trade_category,
                "reason": reason,
            }

        unpriced = [gap(i, i.review_notes or "No price") for i in items if i.total_price is None and not i.is_excluded]
        needs_review = [
            gap(i, i.review_notes or f"Low-confidence mapping ({i.mapping_confidence})")
            for i in items if i.requires_review and not i.is_excluded
        ]
        excluded = [gap(i, i.exclusion_reason or "Excluded from pricing") for i in items if i.is_excluded]
        return {
            "project_id": project_id,
            "unpriced_count": len(unpriced),
            "needs_review_count": len(needs_review),
            "excluded_count": len(excluded),
            "unpriced": unpriced,
            "needs_review": needs_review,
            "excluded": excluded,
        }

    async def update_item_price(
        self, db: AsyncSession, item_id: int, unit_rate: float, notes: str | None = None
    ) -> BOQItem | None:
        item = await db.get(BOQItem, item_id)
        if item is None:
            return None
        item.unit_rate = round(unit_rate, 2)
        item.total_price = round(unit_rate * item.quantity, 2)
        item.requires_review = False
        item.review_notes = notes
        await db.commit()
        await db.refresh(item)
        return item
