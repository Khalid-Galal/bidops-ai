"""Configurable weighted scoring + ranking + comparison for package offers.

Sub-scores per offer (0-100): price, delivery_time, technical_compliance,
supplier_rating, payment_terms. overall = sum(weight*sub)/sum(weight) using
rules.scoring.weights. Pure logic — no LLM.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.package import Package
from app.models.supplier import Supplier, SupplierOffer
from app.services.rules.rules_service import RulesService

_NEUTRAL = 50.0
_TERMINAL = (OfferStatus.SELECTED.value, OfferStatus.REJECTED.value)


class ScoringService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    @staticmethod
    def _ratio_score(value: float | None, best: float | None) -> float:
        """Lower-is-better ratio score: 100 when value == best (the minimum).

        Returns the neutral 50 only when NO offer has a value (best is None).
        When other offers have a value but this offer's is missing or <= 0, it
        returns 0 — a missing price/delivery is treated as the worst commercial
        position, so interim rankings made before all data is entered will
        penalize incomplete offers (rather than reward them with a neutral 50).
        """
        if best is None:
            return _NEUTRAL
        if not value or value <= 0:
            return 0.0
        return round(min(100.0, 100.0 * best / value), 1)

    @staticmethod
    def _net_days(payment_terms: str | None) -> int | None:
        """Parse the first integer in a payment-terms string (e.g. 'Net 30'->30,
        '30 days'->30). Returns None when no integer is present."""
        if not payment_terms:
            return None
        match = re.search(r"\d+", payment_terms)
        return int(match.group()) if match else None

    @classmethod
    def _payment_score(cls, payment_terms: str | None, max_net: int | None) -> float:
        """Score payment terms higher-is-better (longer net-days = more
        buyer-favorable cash flow); neutral 50 when the terms are unparseable
        or no offer in the package has parseable terms."""
        net = cls._net_days(payment_terms)
        if net is None or not max_net:
            return _NEUTRAL
        return round(min(100.0, net / max_net * 100.0), 1)

    @staticmethod
    def _band(score: float, thresholds) -> str:
        if score >= thresholds.excellent:
            return "excellent"
        if score >= thresholds.good:
            return "good"
        if score >= thresholds.acceptable:
            return "acceptable"
        if score >= thresholds.poor:
            return "poor"
        return "unacceptable"

    async def _offers(self, db: AsyncSession, package_id: int) -> list[SupplierOffer]:
        return list(
            (
                await db.execute(
                    select(SupplierOffer)
                    .where(SupplierOffer.package_id == package_id)
                    .order_by(SupplierOffer.id)
                )
            ).scalars().all()
        )

    async def score_package(self, db: AsyncSession, package_id: int) -> dict:
        offers = await self._offers(db, package_id)
        scoring = self._rules().scoring
        weights = scoring.weights.model_dump()
        wsum = sum(weights.values()) or 1.0

        prices = [o.total_price for o in offers if o.total_price and o.total_price > 0]
        min_price = min(prices) if prices else None
        deliveries = [o.delivery_weeks for o in offers if o.delivery_weeks and o.delivery_weeks > 0]
        min_delivery = min(deliveries) if deliveries else None
        nets = [n for n in (self._net_days(o.payment_terms) for o in offers) if n]
        max_net = max(nets) if nets else None

        # Preload suppliers in one query to avoid an N+1 per-offer db.get.
        supplier_ids = {o.supplier_id for o in offers}
        suppliers = (
            {
                s.id: s
                for s in (
                    await db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
                ).scalars().all()
            }
            if supplier_ids
            else {}
        )

        scored: list[tuple] = []
        for offer in offers:
            supplier = suppliers.get(offer.supplier_id)
            technical = offer.technical_score
            if technical is None and offer.compliance_analysis:
                technical = offer.compliance_analysis.get("compliance_score")
            sub = {
                "price": self._ratio_score(offer.total_price, min_price),
                "delivery_time": self._ratio_score(offer.delivery_weeks, min_delivery),
                "technical_compliance": float(technical) if technical is not None else _NEUTRAL,
                "supplier_rating": (
                    round(supplier.rating / 5.0 * 100.0, 1)
                    if supplier and supplier.rating
                    else _NEUTRAL
                ),
                # Longer net-days = better (buyer-favorable); neutral when
                # unparseable or no offer has parseable terms.
                "payment_terms": self._payment_score(offer.payment_terms, max_net),
            }
            overall = round(
                sum(weights.get(k, 0.0) * sub.get(k, 0.0) for k in weights) / wsum, 1
            )
            offer.commercial_score = sub["price"]
            offer.technical_score = sub["technical_compliance"]
            offer.overall_score = overall
            offer.evaluated_at = datetime.now(timezone.utc)
            if offer.status not in _TERMINAL:
                offer.status = OfferStatus.EVALUATED.value
            scored.append((offer, sub, overall, supplier.name if supplier else ""))

        scored.sort(key=lambda r: r[2], reverse=True)
        ranking = []
        for rank, (offer, sub, overall, supplier_name) in enumerate(scored, 1):
            offer.rank = rank
            ranking.append(
                {
                    "offer_id": offer.id,
                    "supplier_name": supplier_name,
                    "subscores": sub,
                    "overall_score": overall,
                    "rank": rank,
                    "band": self._band(overall, scoring.thresholds),
                }
            )
        await db.commit()
        return {
            "package_id": package_id,
            "offers_scored": len(offers),
            "weights": weights,
            "ranking": ranking,
        }

    async def compare(self, db: AsyncSession, package_id: int) -> dict:
        package = await db.get(Package, package_id)
        if package is None:
            raise ValueError(f"Package {package_id} not found")
        offers = list(
            (
                await db.execute(
                    select(SupplierOffer)
                    .where(SupplierOffer.package_id == package_id)
                    .order_by(SupplierOffer.overall_score.desc().nullslast(), SupplierOffer.id)
                )
            ).scalars().all()
        )
        # Preload suppliers in one query to avoid an N+1 per-offer db.get.
        supplier_ids = {o.supplier_id for o in offers}
        suppliers = (
            {
                s.id: s
                for s in (
                    await db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
                ).scalars().all()
            }
            if supplier_ids
            else {}
        )
        rows = []
        prices = []
        for offer in offers:
            supplier = suppliers.get(offer.supplier_id)
            if offer.total_price:
                prices.append(offer.total_price)
            rows.append(
                {
                    "offer_id": offer.id,
                    "supplier_id": offer.supplier_id,
                    "supplier_name": supplier.name if supplier else "",
                    "total_price": offer.total_price,
                    "currency": offer.currency,
                    "validity_days": offer.validity_days,
                    "delivery_weeks": offer.delivery_weeks,
                    "payment_terms": offer.payment_terms,
                    "commercial_score": offer.commercial_score,
                    "technical_score": offer.technical_score,
                    "overall_score": offer.overall_score,
                    "rank": offer.rank,
                    "status": offer.status,
                    "exclusions_count": len(offer.exclusions or []),
                    "deviations_count": len(offer.deviations or []),
                }
            )
        currency = next((o.currency for o in offers if o.currency), self._rules().commercial.currency)
        return {
            "package_id": package_id,
            "package_name": package.name,
            "total_offers": len(offers),
            "evaluated_offers": len([o for o in offers if o.overall_score is not None]),
            "currency": currency,
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "price_avg": round(sum(prices) / len(prices), 2) if prices else None,
            "offers": rows,
        }
