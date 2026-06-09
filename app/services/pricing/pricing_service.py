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

    async def populate_from_offer(
        self,
        db: AsyncSession,
        offer_id: int,
        *,
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

        m = rules.commercial.markup
        overhead = round(cost_subtotal * m.overhead, 2)
        profit = round(cost_subtotal * m.profit, 2)
        contingency = round(cost_subtotal * m.contingency, 2)
        risk = round(cost_subtotal * m.risk, 2)
        markup_total = round(overhead + profit + contingency + risk, 2)
        selling_before_vat = round(cost_subtotal + markup_total, 2)
        vat_rate = rules.commercial.vat_rate
        vat_amount = round(selling_before_vat * vat_rate, 2)
        grand_total = round(selling_before_vat + vat_amount, 2)

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

        # The summary reports the commercial/selling currency from rules
        # (markups + VAT are applied per the rules' commercial config). The
        # per-item currency is the supplier offer's cost currency and is only a
        # fallback when rules carry no commercial currency.
        currency = rules.commercial.currency or next(
            (i.currency for i in priced if i.currency), None
        )
        return {
            "project_id": project_id,
            "currency": currency,
            "total_items": len(items),
            "priced_items": len(priced),
            "unpriced_items": len(items) - len(priced),
            "completion_rate": round(len(priced) / len(items) * 100, 1) if items else 0.0,
            "cost_subtotal": cost_subtotal,
            "markups": {
                "overhead": overhead,
                "profit": profit,
                "contingency": contingency,
                "risk": risk,
                "markup_total": markup_total,
            },
            "selling_before_vat": selling_before_vat,
            "vat_rate": vat_rate,
            "vat_amount": vat_amount,
            "grand_total": grand_total,
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

        unpriced = [gap(i, i.review_notes or "No price") for i in items if not i.total_price and not i.is_excluded]
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
