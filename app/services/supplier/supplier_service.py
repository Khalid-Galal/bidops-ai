"""Supplier management: CRUD, search, trade matching, blacklist, Excel I/O.

Single-user/global for now (organization_id stays NULL; auth is Phase 15).
Trade-category matching is done in Python — SQLAlchemy JSON .contains() does
not work on SQLite/aiosqlite.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier

# Editable supplier fields shared by create/update (keeps DRY).
_SETTABLE = (
    "name", "name_ar", "code", "emails", "trade_categories", "phone", "fax",
    "address", "website", "contact_name", "contact_email", "contact_phone",
    "region", "country", "rating", "preferred_language", "preferred_format",
    "notes",
)


class SupplierService:
    async def _next_code(self, db: AsyncSession) -> str:
        count = (await db.execute(select(func.count(Supplier.id)))).scalar() or 0
        return f"SUP-{count + 1:04d}"

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        emails: list[str],
        trade_categories: list[str],
        **fields,
    ) -> Supplier:
        code = fields.pop("code", None) or await self._next_code(db)
        supplier = Supplier(
            organization_id=None,
            name=name,
            code=code,
            emails=emails or [],
            trade_categories=trade_categories or [],
            **{k: v for k, v in fields.items() if k in _SETTABLE},
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    async def get(self, db: AsyncSession, supplier_id: int) -> Supplier | None:
        return await db.get(Supplier, supplier_id)

    async def update(
        self, db: AsyncSession, supplier_id: int, **fields
    ) -> Supplier | None:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            return None
        for key, value in fields.items():
            if value is None:
                continue
            if key in _SETTABLE or key == "is_active":
                setattr(supplier, key, value)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    async def list_suppliers(
        self,
        db: AsyncSession,
        *,
        query: str | None = None,
        trade: str | None = None,
        region: str | None = None,
        is_active: bool | None = True,
        min_rating: float | None = None,
    ) -> list[Supplier]:
        stmt = select(Supplier)
        if query:
            term = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Supplier.name.ilike(term),
                    Supplier.code.ilike(term),
                    Supplier.contact_name.ilike(term),
                )
            )
        if region:
            stmt = stmt.where(Supplier.region == region)
        if is_active is not None:
            stmt = stmt.where(Supplier.is_active == is_active)
        if min_rating is not None:
            stmt = stmt.where(Supplier.rating >= min_rating)
        stmt = stmt.order_by(Supplier.name)
        rows = list((await db.execute(stmt)).scalars().all())
        # Trade filter in Python (JSON .contains is not portable to SQLite).
        if trade:
            rows = [s for s in rows if trade in (s.trade_categories or [])]
        return rows

    async def suppliers_for_trade(
        self, db: AsyncSession, trade: str, limit: int = 50
    ) -> list[Supplier]:
        stmt = (
            select(Supplier)
            .where(Supplier.is_active.is_(True), Supplier.is_blacklisted.is_(False))
            .order_by(Supplier.rating.desc().nullslast(), Supplier.name)
        )
        rows = [
            s
            for s in (await db.execute(stmt)).scalars().all()
            if trade in (s.trade_categories or [])
        ]
        return rows[:limit]

    async def blacklist(
        self, db: AsyncSession, supplier_id: int, reason: str
    ) -> Supplier | None:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            return None
        supplier.is_blacklisted = True
        supplier.is_active = False
        supplier.blacklist_reason = reason
        await db.commit()
        await db.refresh(supplier)
        return supplier
