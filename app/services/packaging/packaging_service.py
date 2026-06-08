"""Groups classified BOQ items into trade-based procurement packages."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.package import Package
from app.schemas.rules import RulesConfig
from app.services.rules import get_rules_service


class PackagingService:
    """Generate, list, and inspect trade packages for a project."""

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self._rules = rules or get_rules_service().load()

    def _project_code(self, project_id: int) -> str:
        return f"P{project_id:04d}"

    def _package_code(self, project_id: int, trade: str, seq: int) -> str:
        abbr = self._rules.naming.trade_abbreviations.get(trade, trade[:3].upper())
        try:
            return self._rules.naming.package_code_format.format(
                project_code=self._project_code(project_id),
                trade_abbr=abbr,
                seq=seq,
            )
        except (KeyError, IndexError, ValueError):
            return f"PKG-{self._project_code(project_id)}-{abbr}-{seq:03d}"

    async def generate(self, db: AsyncSession, project_id: int) -> dict:
        """(Re)generate packages for a project from its classified BOQ items.

        Idempotent: deletes existing packages + unassigns items first, then
        groups classified items by trade and splits groups larger than
        rules.packaging.max_items_per_package. Uncategorized items
        (trade_category is None) are left unassigned and counted.
        """
        # Reset: unassign all items, delete existing packages for the project.
        await db.execute(
            update(BOQItem)
            .where(BOQItem.project_id == project_id)
            .values(package_id=None)
        )
        await db.execute(delete(Package).where(Package.project_id == project_id))
        await db.flush()

        items = (
            await db.execute(
                select(BOQItem)
                .where(BOQItem.project_id == project_id)
                .order_by(BOQItem.client_row_index)
            )
        ).scalars().all()

        groups: dict[str, list[BOQItem]] = defaultdict(list)
        unassigned = 0
        for item in items:
            if item.trade_category:
                groups[item.trade_category].append(item)
            else:
                unassigned += 1

        max_items = max(1, self._rules.packaging.max_items_per_package)
        by_trade: Counter[str] = Counter()
        seq = 0
        assigned = 0

        for trade in sorted(groups):
            trade_items = groups[trade]
            # split into chunks of at most max_items
            chunks = [
                trade_items[i : i + max_items]
                for i in range(0, len(trade_items), max_items)
            ]
            multi = len(chunks) > 1
            for part, chunk in enumerate(chunks, start=1):
                seq += 1
                name = f"{trade.replace('_', ' ').title()} Works"
                if multi:
                    name = f"{name} (Part {part})"
                package = Package(
                    project_id=project_id,
                    name=name,
                    code=self._package_code(project_id, trade, seq),
                    trade_category=trade,
                    total_items=len(chunk),
                )
                db.add(package)
                await db.flush()  # assign package.id
                for item in chunk:
                    item.package_id = package.id
                by_trade[trade] += 1
                assigned += len(chunk)

        await db.commit()
        return {
            "project_id": project_id,
            "packages_created": seq,
            "items_assigned": assigned,
            "items_unassigned": unassigned,
            "by_trade": dict(by_trade),
        }

    async def list_packages(self, db: AsyncSession, project_id: int) -> list[Package]:
        result = await db.execute(
            select(Package)
            .where(Package.project_id == project_id)
            .order_by(Package.code)
        )
        return list(result.scalars().all())

    async def get_package(self, db: AsyncSession, package_id: int) -> Package | None:
        return await db.get(Package, package_id)

    async def get_package_items(
        self, db: AsyncSession, package_id: int
    ) -> list[BOQItem]:
        result = await db.execute(
            select(BOQItem)
            .where(BOQItem.package_id == package_id)
            .order_by(BOQItem.client_row_index)
        )
        return list(result.scalars().all())
