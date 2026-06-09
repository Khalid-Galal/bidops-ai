"""Historical price learning: corpus management + benchmark suggestions.

Matching reuses the deterministic Phase 11 fuzzy matcher; an optional
semantic_scorer(a, b) -> float can be injected to blend an embedding score
(the local sentence-transformer is a dependency but is intentionally not wired
into the default/tested path). Pure logic — no Gemini key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical import HistoricalPrice
from app.services.pricing.line_item_matcher import DEFAULT_THRESHOLD, match_score

_DEFAULT_TOP_K = 5

# Editable corpus fields shared by add/import (keeps DRY).
_SETTABLE = (
    "description", "description_ar", "unit", "rate", "currency", "trade_category",
)


class HistoricalService:
    def __init__(self, semantic_scorer=None) -> None:
        self._semantic_scorer = semantic_scorer

    async def add(
        self,
        db: AsyncSession,
        *,
        description: str,
        rate: float,
        source: str = "manual",
        source_project_id: int | None = None,
        recorded_at: datetime | None = None,
        **fields,
    ) -> HistoricalPrice:
        rec = HistoricalPrice(
            description=description,
            rate=rate,
            source=source,
            source_project_id=source_project_id,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            **{k: v for k, v in fields.items() if k in _SETTABLE},
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def list_records(
        self, db: AsyncSession, *, trade: str | None = None, limit: int = 200
    ) -> list[HistoricalPrice]:
        stmt = select(HistoricalPrice)
        if trade:
            stmt = stmt.where(HistoricalPrice.trade_category == trade)
        stmt = stmt.order_by(HistoricalPrice.id.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def _benchmark(rates: list[float], currency: str | None) -> dict:
        if not rates:
            return {
                "count": 0, "min": None, "max": None, "avg": None,
                "median": None, "suggested_rate": None, "currency": currency,
            }
        med = round(median(rates), 2)
        return {
            "count": len(rates),
            "min": round(min(rates), 2),
            "max": round(max(rates), 2),
            "avg": round(mean(rates), 2),
            "median": med,
            "suggested_rate": med,
            "currency": currency,
        }

    async def suggest(
        self,
        db: AsyncSession,
        description: str,
        *,
        unit: str | None = None,
        trade: str | None = None,
        top_k: int = _DEFAULT_TOP_K,
        min_score: float = DEFAULT_THRESHOLD,
        exclude_project_id: int | None = None,
    ) -> dict:
        stmt = select(HistoricalPrice)
        if trade:
            stmt = stmt.where(HistoricalPrice.trade_category == trade)
        if exclude_project_id is not None:
            stmt = stmt.where(
                or_(
                    HistoricalPrice.source_project_id != exclude_project_id,
                    HistoricalPrice.source_project_id.is_(None),
                )
            )
        records = list((await db.execute(stmt)).scalars().all())

        scored: list[tuple[HistoricalPrice, float]] = []
        for rec in records:
            score = match_score(description, rec.description)
            if self._semantic_scorer is not None:
                score = max(score, float(self._semantic_scorer(description, rec.description)))
            if score >= min_score:
                scored.append((rec, round(score, 4)))
        scored.sort(key=lambda rs: rs[1], reverse=True)
        top = scored[:top_k]

        rates = [rec.rate for rec, _ in top]
        currency = next((rec.currency for rec, _ in top if rec.currency), None)
        matches = [
            {
                "historical_id": rec.id,
                "description": rec.description,
                "unit": rec.unit,
                "rate": rec.rate,
                "currency": rec.currency,
                "source": rec.source,
                "source_project_id": rec.source_project_id,
                "similarity": score,
            }
            for rec, score in top
        ]
        return {
            "query": description,
            "trade": trade,
            "benchmark": self._benchmark(rates, currency),
            "matches": matches,
        }
