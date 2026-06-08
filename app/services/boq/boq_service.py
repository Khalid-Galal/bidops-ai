"""Orchestrates BOQ parsing + trade classification + persistence."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.schemas.rules import RulesConfig
from app.services.boq.boq_parser import parse_boq_workbook
from app.services.boq.trade_classifier import classify_trade
from app.services.rules import get_rules_service


class BOQService:
    """Parse a BOQ workbook into classified, persisted BOQItem rows."""

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self._rules = rules or get_rules_service().load()

    async def parse_and_store(
        self, db: AsyncSession, project_id: int, file_path: str
    ) -> dict:
        """Parse the workbook, classify each row, persist BOQItem rows.

        Returns a summary: {total, classified, uncategorized, by_trade}.
        """
        rows = parse_boq_workbook(file_path, self._rules)
        by_trade: Counter[str] = Counter()
        uncategorized = 0

        for idx, row in enumerate(rows, start=1):
            category, confidence = classify_trade(row.description, self._rules)
            if category is None:
                uncategorized += 1
            else:
                by_trade[category] += 1
            db.add(
                BOQItem(
                    project_id=project_id,
                    line_number=row.line_number or str(idx),
                    section=row.section,
                    description=row.description,
                    unit=row.unit,
                    quantity=row.quantity,
                    client_row_index=row.client_row_index,
                    trade_category=category,
                    classification_confidence=confidence,
                    requires_review=category is None,
                )
            )
        await db.commit()
        return {
            "total": len(rows),
            "classified": len(rows) - uncategorized,
            "uncategorized": uncategorized,
            "by_trade": dict(by_trade),
        }

    async def list_items(
        self, db: AsyncSession, project_id: int
    ) -> list[BOQItem]:
        result = await db.execute(
            select(BOQItem)
            .where(BOQItem.project_id == project_id)
            .order_by(BOQItem.client_row_index)
        )
        return list(result.scalars().all())
