"""Configurable weighted scoring + ranking + comparison for package offers.

Sub-scores per offer (0-100): price, delivery_time, technical_compliance,
supplier_rating, payment_terms. overall = sum(weight*sub)/sum(weight) using
rules.scoring.weights. Pure logic — no LLM.
"""

from __future__ import annotations

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
        """100 when value == best (the minimum); lower as value grows."""
        if best is None:
            return _NEUTRAL
        if not value or value <= 0:
            return 0.0
        return round(min(100.0, 100.0 * best / value), 1)

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

        scored: list[tuple] = []
        for offer in offers:
            supplier = await db.get(Supplier, offer.supplier_id)
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
                "payment_terms": _NEUTRAL,
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
        rows = []
        prices = []
        for offer in offers:
            supplier = await db.get(Supplier, offer.supplier_id)
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
