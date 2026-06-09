"""Indirect-cost engine: percentage-of-direct components, duration-based staff
costs, and a location factor — all configurable via rules.indirects.

Pure logic — no LLM. Direct cost is read from the Phase 11 pricing summary.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pricing.commercial import compute_commercial
from app.services.pricing.pricing_service import PricingService
from app.services.rules.rules_service import RulesService


class IndirectsService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    def _rules(self):
        return self._rules_service.load()

    def compute(
        self,
        direct_cost: float,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        """Return the indirects breakdown for a given direct cost."""
        ind = self._rules().indirects
        percentage_based = {
            name: round(direct_cost * frac, 2)
            for name, frac in ind.percentage_based.items()
        }
        # Compute each role's amount once, then drop roles that contribute
        # nothing (zero monthly_rate or zero duration) so the breakdown stays clean.
        _duration_amounts = {
            role: round(cfg.monthly_rate * duration_months, 2)
            for role, cfg in ind.duration_based.items()
        }
        duration_based = {
            role: amount for role, amount in _duration_amounts.items() if amount != 0.0
        }
        subtotal = round(
            sum(percentage_based.values()) + sum(duration_based.values()), 2
        )
        location_factor = ind.location_factors.get(
            location, ind.location_factors.get("default", 1.0)
        )
        total_indirects = round(subtotal * location_factor, 2)
        return {
            "percentage_based": percentage_based,
            "duration_based": duration_based,
            "duration_months": duration_months,
            "location": location,
            "location_factor": location_factor,
            "subtotal_before_location": subtotal,
            "total_indirects": total_indirects,
        }

    async def indirects_result(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        summary = await PricingService(self._rules_service).pricing_summary(db, project_id)
        direct_cost = summary["cost_subtotal"]
        return {
            "project_id": project_id,
            "currency": summary["currency"],
            "direct_cost": direct_cost,
            "indirects": self.compute(
                direct_cost, duration_months=duration_months, location=location
            ),
        }

    async def project_cost_summary(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        duration_months: int = 0,
        location: str = "default",
    ) -> dict:
        rules = self._rules()
        summary = await PricingService(self._rules_service).pricing_summary(db, project_id)
        direct_cost = summary["cost_subtotal"]
        indirects = self.compute(
            direct_cost, duration_months=duration_months, location=location
        )
        total_cost_base = round(direct_cost + indirects["total_indirects"], 2)
        commercial = compute_commercial(total_cost_base, rules)
        return {
            "project_id": project_id,
            "currency": summary["currency"],
            "direct_cost": direct_cost,
            "indirects": indirects,
            "total_cost_base": total_cost_base,
            "markups": commercial["markups"],
            "selling_before_vat": commercial["selling_before_vat"],
            "vat_rate": commercial["vat_rate"],
            "vat_amount": commercial["vat_amount"],
            "grand_total": commercial["grand_total"],
        }
