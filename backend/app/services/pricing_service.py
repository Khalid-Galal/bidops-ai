"""Pricing population and analysis service."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings, get_rules
from app.database import get_db_context
from app.models import BOQItem, Package, Project, Document
from app.models.supplier import SupplierOffer
from app.models.base import OfferStatus, PackageStatus

settings = get_settings()
rules = get_rules()


class PricingService:
    """Service for pricing population and analysis.

    Handles:
    - Populating BOQ with selected offer prices
    - Price analysis and statistics
    - Markup calculations
    - Cost breakdown analysis
    - Budget vs actual comparison
    """

    # Default markup percentages by trade
    DEFAULT_MARKUPS = {
        "CIVIL": 0.10,
        "CONCRETE": 0.12,
        "STRUCTURAL_STEEL": 0.08,
        "MASONRY": 0.12,
        "WATERPROOFING": 0.15,
        "ROOFING": 0.12,
        "DOORS_WINDOWS": 0.10,
        "FINISHES": 0.15,
        "MEP_MECHANICAL": 0.10,
        "MEP_ELECTRICAL": 0.10,
        "MEP_PLUMBING": 0.12,
        "FIRE_PROTECTION": 0.10,
        "ELEVATORS": 0.08,
        "LANDSCAPING": 0.15,
        "FURNITURE": 0.12,
        "GENERAL": 0.10,
    }

    async def populate_from_offer(
        self,
        offer_id: int,
        apply_markup: bool = False,
        markup_percentage: Optional[float] = None,
    ) -> dict:
        """Populate BOQ prices from a selected offer.

        Args:
            offer_id: Selected offer ID
            apply_markup: Whether to apply markup
            markup_percentage: Custom markup (overrides trade defaults)

        Returns:
            Population results
        """
        async with get_db_context() as db:
            # Get offer with line items
            result = await db.execute(
                select(SupplierOffer)
                .options(
                    selectinload(SupplierOffer.package).selectinload(Package.items),
                )
                .where(SupplierOffer.id == offer_id)
            )
            offer = result.scalar_one_or_none()

            if not offer:
                raise ValueError(f"Offer not found: {offer_id}")

            if offer.status != OfferStatus.SELECTED:
                raise ValueError("Only selected offers can be used for pricing")

            if not offer.line_items:
                raise ValueError("Offer has no line items to populate")

            populated = 0
            skipped = 0
            total_value = 0.0

            # Create mapping from offer line items
            # Try to match by description similarity
            offer_items = {self._normalize_desc(item.get("description", "")): item
                          for item in offer.line_items}

            for boq_item in offer.package.items:
                normalized_desc = self._normalize_desc(boq_item.description)

                # Try exact match first
                matched_item = offer_items.get(normalized_desc)

                # Try partial match if no exact match
                if not matched_item:
                    for offer_desc, item in offer_items.items():
                        if self._descriptions_match(normalized_desc, offer_desc):
                            matched_item = item
                            break

                if matched_item:
                    unit_rate = float(matched_item.get("unit_rate", 0) or
                                     matched_item.get("rate", 0) or 0)

                    if unit_rate > 0:
                        # Apply markup if requested
                        if apply_markup:
                            if markup_percentage is not None:
                                markup = markup_percentage
                            else:
                                markup = self.DEFAULT_MARKUPS.get(
                                    boq_item.trade_category, 0.10
                                )
                            unit_rate = unit_rate * (1 + markup)

                        boq_item.unit_rate = round(unit_rate, 2)
                        boq_item.total_price = round(unit_rate * boq_item.quantity, 2)
                        boq_item.price_source = f"offer:{offer_id}"
                        total_value += boq_item.total_price
                        populated += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1

            await db.commit()

            return {
                "offer_id": offer_id,
                "package_id": offer.package_id,
                "items_populated": populated,
                "items_skipped": skipped,
                "total_value": round(total_value, 2),
                "currency": offer.currency,
            }

    def _normalize_desc(self, description: str) -> str:
        """Normalize description for matching."""
        import re
        # Remove special chars, lowercase, remove extra spaces
        desc = re.sub(r'[^\w\s]', '', description.lower())
        desc = ' '.join(desc.split())
        return desc

    def _descriptions_match(self, desc1: str, desc2: str, threshold: float = 0.7) -> bool:
        """Check if two descriptions match using simple similarity."""
        words1 = set(desc1.split())
        words2 = set(desc2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold

    async def calculate_package_totals(
        self,
        package_id: int,
    ) -> dict:
        """Calculate total pricing for a package.

        Args:
            package_id: Package ID

        Returns:
            Package pricing totals
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(Package)
                .options(selectinload(Package.items))
                .where(Package.id == package_id)
            )
            package = result.scalar_one_or_none()

            if not package:
                raise ValueError(f"Package not found: {package_id}")

            items_with_price = [i for i in package.items if i.total_price]
            items_without_price = [i for i in package.items if not i.total_price]

            total = sum(i.total_price for i in items_with_price)

            return {
                "package_id": package_id,
                "package_name": package.name,
                "total_items": len(package.items),
                "priced_items": len(items_with_price),
                "unpriced_items": len(items_without_price),
                "subtotal": round(total, 2),
                "currency": package.currency or "USD",
                "completion_rate": round(
                    len(items_with_price) / len(package.items) * 100, 1
                ) if package.items else 0,
            }

    async def calculate_project_totals(
        self,
        project_id: int,
    ) -> dict:
        """Calculate total pricing for entire project.

        Args:
            project_id: Project ID

        Returns:
            Project pricing totals
        """
        async with get_db_context() as db:
            # Get project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Get all BOQ items
            result = await db.execute(
                select(BOQItem).where(BOQItem.project_id == project_id)
            )
            all_items = list(result.scalars().all())

            # Get packages
            result = await db.execute(
                select(Package).where(Package.project_id == project_id)
            )
            packages = list(result.scalars().all())

            # Calculate by trade
            by_trade = {}
            for item in all_items:
                trade = item.trade_category or "GENERAL"
                if trade not in by_trade:
                    by_trade[trade] = {"count": 0, "total": 0.0, "priced": 0}
                by_trade[trade]["count"] += 1
                if item.total_price:
                    by_trade[trade]["total"] += item.total_price
                    by_trade[trade]["priced"] += 1

            # Calculate overall totals
            total_value = sum(i.total_price or 0 for i in all_items)
            priced_items = len([i for i in all_items if i.total_price])

            return {
                "project_id": project_id,
                "project_name": project.name,
                "total_packages": len(packages),
                "total_items": len(all_items),
                "priced_items": priced_items,
                "unpriced_items": len(all_items) - priced_items,
                "total_value": round(total_value, 2),
                "by_trade": {
                    trade: {
                        "count": data["count"],
                        "priced": data["priced"],
                        "total": round(data["total"], 2),
                    }
                    for trade, data in by_trade.items()
                },
                "completion_rate": round(
                    priced_items / len(all_items) * 100, 1
                ) if all_items else 0,
            }

    async def apply_markup_to_package(
        self,
        package_id: int,
        markup_percentage: float,
        only_unpriced: bool = False,
    ) -> dict:
        """Apply markup to package items.

        Args:
            package_id: Package ID
            markup_percentage: Markup percentage (0.10 = 10%)
            only_unpriced: Only apply to items without prices

        Returns:
            Application results
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(Package)
                .options(selectinload(Package.items))
                .where(Package.id == package_id)
            )
            package = result.scalar_one_or_none()

            if not package:
                raise ValueError(f"Package not found: {package_id}")

            updated = 0
            for item in package.items:
                if only_unpriced and item.unit_rate:
                    continue

                if item.unit_rate:
                    original_rate = item.unit_rate
                    item.unit_rate = round(original_rate * (1 + markup_percentage), 2)
                    item.total_price = round(item.unit_rate * item.quantity, 2)
                    updated += 1

            await db.commit()

            return {
                "package_id": package_id,
                "items_updated": updated,
                "markup_applied": f"{markup_percentage * 100:.1f}%",
            }

    async def get_price_comparison(
        self,
        package_id: int,
    ) -> dict:
        """Get price comparison across all offers for a package.

        Args:
            package_id: Package ID

        Returns:
            Price comparison data
        """
        async with get_db_context() as db:
            # Get package with items
            result = await db.execute(
                select(Package)
                .options(selectinload(Package.items))
                .where(Package.id == package_id)
            )
            package = result.scalar_one_or_none()

            if not package:
                raise ValueError(f"Package not found: {package_id}")

            # Get all offers
            result = await db.execute(
                select(SupplierOffer)
                .options(selectinload(SupplierOffer.supplier))
                .where(SupplierOffer.package_id == package_id)
            )
            offers = list(result.scalars().all())

            comparison = {
                "package_id": package_id,
                "package_name": package.name,
                "boq_items": [],
            }

            for item in package.items:
                item_data = {
                    "id": item.id,
                    "line_number": item.line_number,
                    "description": item.description[:100],
                    "unit": item.unit,
                    "quantity": item.quantity,
                    "prices": {},
                }

                # Find matching prices from each offer
                normalized_desc = self._normalize_desc(item.description)

                for offer in offers:
                    if not offer.line_items:
                        continue

                    for offer_item in offer.line_items:
                        offer_desc = self._normalize_desc(
                            offer_item.get("description", "")
                        )
                        if self._descriptions_match(normalized_desc, offer_desc, 0.6):
                            rate = offer_item.get("unit_rate") or offer_item.get("rate", 0)
                            item_data["prices"][offer.supplier.name] = {
                                "unit_rate": rate,
                                "total": rate * item.quantity if rate else 0,
                            }
                            break

                # Calculate statistics
                rates = [p["unit_rate"] for p in item_data["prices"].values() if p["unit_rate"]]
                if rates:
                    item_data["min_rate"] = min(rates)
                    item_data["max_rate"] = max(rates)
                    item_data["avg_rate"] = sum(rates) / len(rates)
                    item_data["spread"] = max(rates) - min(rates)

                comparison["boq_items"].append(item_data)

            return comparison

    async def get_cost_breakdown(
        self,
        project_id: int,
    ) -> dict:
        """Get detailed cost breakdown for a project.

        Args:
            project_id: Project ID

        Returns:
            Cost breakdown data
        """
        async with get_db_context() as db:
            # Get all priced items
            result = await db.execute(
                select(BOQItem).where(
                    BOQItem.project_id == project_id,
                    BOQItem.total_price != None,
                )
            )
            items = list(result.scalars().all())

            # Group by trade
            by_trade = {}
            for item in items:
                trade = item.trade_category or "GENERAL"
                if trade not in by_trade:
                    by_trade[trade] = {
                        "items": [],
                        "total": 0.0,
                        "count": 0,
                    }
                by_trade[trade]["items"].append({
                    "description": item.description[:80],
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_rate": item.unit_rate,
                    "total": item.total_price,
                })
                by_trade[trade]["total"] += item.total_price
                by_trade[trade]["count"] += 1

            # Calculate percentages
            grand_total = sum(t["total"] for t in by_trade.values())

            breakdown = {
                "project_id": project_id,
                "grand_total": round(grand_total, 2),
                "trades": [],
            }

            for trade, data in sorted(by_trade.items(), key=lambda x: -x[1]["total"]):
                breakdown["trades"].append({
                    "trade": trade,
                    "count": data["count"],
                    "total": round(data["total"], 2),
                    "percentage": round(data["total"] / grand_total * 100, 1) if grand_total else 0,
                    "top_items": sorted(
                        data["items"], key=lambda x: -x["total"]
                    )[:5],  # Top 5 items by value
                })

            return breakdown

    async def update_item_price(
        self,
        item_id: int,
        unit_rate: float,
        source: Optional[str] = None,
    ) -> BOQItem:
        """Update a single BOQ item price.

        Args:
            item_id: BOQ item ID
            unit_rate: New unit rate
            source: Price source description

        Returns:
            Updated item
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(BOQItem).where(BOQItem.id == item_id)
            )
            item = result.scalar_one_or_none()

            if not item:
                raise ValueError(f"BOQ item not found: {item_id}")

            item.unit_rate = round(unit_rate, 2)
            item.total_price = round(unit_rate * item.quantity, 2)
            if source:
                item.price_source = source

            await db.commit()
            await db.refresh(item)

            return item

    async def bulk_update_prices(
        self,
        updates: list[dict],
    ) -> dict:
        """Bulk update BOQ item prices.

        Args:
            updates: List of {item_id, unit_rate, source?}

        Returns:
            Update results
        """
        async with get_db_context() as db:
            updated = 0
            failed = 0
            errors = []

            for upd in updates:
                try:
                    item_id = upd["item_id"]
                    unit_rate = float(upd["unit_rate"])

                    result = await db.execute(
                        select(BOQItem).where(BOQItem.id == item_id)
                    )
                    item = result.scalar_one_or_none()

                    if item:
                        item.unit_rate = round(unit_rate, 2)
                        item.total_price = round(unit_rate * item.quantity, 2)
                        if "source" in upd:
                            item.price_source = upd["source"]
                        updated += 1
                    else:
                        failed += 1
                        errors.append(f"Item {item_id} not found")

                except Exception as e:
                    failed += 1
                    errors.append(str(e))

            await db.commit()

            return {
                "updated": updated,
                "failed": failed,
                "errors": errors[:10],
            }

    async def copy_prices_between_packages(
        self,
        source_package_id: int,
        target_package_id: int,
        match_by: str = "description",
    ) -> dict:
        """Copy prices from one package to another.

        Args:
            source_package_id: Source package ID
            target_package_id: Target package ID
            match_by: Matching strategy (description, line_number)

        Returns:
            Copy results
        """
        async with get_db_context() as db:
            # Get source items with prices
            result = await db.execute(
                select(BOQItem).where(
                    BOQItem.package_id == source_package_id,
                    BOQItem.unit_rate != None,
                )
            )
            source_items = list(result.scalars().all())

            # Get target items
            result = await db.execute(
                select(BOQItem).where(BOQItem.package_id == target_package_id)
            )
            target_items = list(result.scalars().all())

            # Create mapping
            if match_by == "line_number":
                source_map = {i.line_number: i for i in source_items}
                match_func = lambda t: source_map.get(t.line_number)
            else:
                source_map = {self._normalize_desc(i.description): i for i in source_items}
                def match_func(target):
                    target_desc = self._normalize_desc(target.description)
                    # Try exact match
                    if target_desc in source_map:
                        return source_map[target_desc]
                    # Try fuzzy match
                    for src_desc, src_item in source_map.items():
                        if self._descriptions_match(target_desc, src_desc):
                            return src_item
                    return None

            copied = 0
            for target in target_items:
                source = match_func(target)
                if source and source.unit_rate:
                    target.unit_rate = source.unit_rate
                    target.total_price = round(source.unit_rate * target.quantity, 2)
                    target.price_source = f"copied:package:{source_package_id}"
                    copied += 1

            await db.commit()

            return {
                "source_package_id": source_package_id,
                "target_package_id": target_package_id,
                "items_copied": copied,
                "total_target_items": len(target_items),
            }
