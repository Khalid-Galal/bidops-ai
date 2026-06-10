"""Links project documents to packages via semantic search over indexed chunks."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boq import BOQItem
from app.models.document import Document
from app.models.package import Package, PackageDocument

logger = logging.getLogger(__name__)

_EXCERPT_LEN = 300
_DEFAULT_TOP_K = 30
_DEFAULT_MIN_SCORE = 0.3
_DEFAULT_MAX_DOCS = 10
_QUERY_ITEM_SAMPLE = 8  # BOQ item descriptions to fold into the query


class DocumentLinker:
    """Find and persist the documents most relevant to each package.

    The search dependency is injectable so the aggregation/persistence logic is
    testable without ChromaDB; production lazily resolves the real service.
    """

    def __init__(self, search_service=None) -> None:
        self._injected = search_service

    def _search(self):
        if self._injected is not None:
            return self._injected
        from app.api.search import _get_search_service

        return _get_search_service()

    async def _build_query(self, db: AsyncSession, package: Package) -> str:
        descs = (
            await db.execute(
                select(BOQItem.description)
                .where(BOQItem.package_id == package.id)
                .order_by(BOQItem.client_row_index)
                .limit(_QUERY_ITEM_SAMPLE)
            )
        ).scalars().all()
        trade = (package.trade_category or "").replace("_", " ")
        return f"{trade} specifications drawings requirements " + " ".join(descs)

    async def link_package(
        self,
        db: AsyncSession,
        package: Package,
        *,
        top_k: int = _DEFAULT_TOP_K,
        min_score: float = _DEFAULT_MIN_SCORE,
        max_docs: int = _DEFAULT_MAX_DOCS,
    ) -> int:
        """(Re)link the most relevant documents to a package. Returns link count."""
        query = await self._build_query(db, package)
        try:
            hits = self._search().search(
                project_id=package.project_id, query=query, top_k=top_k, mode="semantic"
            )
        except Exception as exc:  # noqa: BLE001 - search infra failure -> no links, not a crash
            logger.warning(
                "Document search failed for package %s; linking 0 documents: %s",
                package.id,
                exc,
            )
            hits = []

        # Never link superseded/duplicate documents — pricing must flow from
        # the latest revision only (Phase 7C).
        superseded_ids = set(
            (
                await db.execute(
                    select(Document.id).where(
                        Document.project_id == package.project_id,
                        Document.is_superseded.is_(True),
                    )
                )
            ).scalars().all()
        )

        # Aggregate hits per document: keep max score + its best excerpt/page.
        best: dict[int, dict] = {}
        for h in hits:
            doc_id = getattr(h, "document_id", None)
            if doc_id is None:
                continue
            if doc_id in superseded_ids:
                continue
            score = float(getattr(h, "score", 0.0) or 0.0)
            cur = best.get(doc_id)
            if cur is None or score > cur["score"]:
                best[doc_id] = {
                    "score": score,
                    "excerpt": (getattr(h, "text", "") or "")[:_EXCERPT_LEN],
                    "page": getattr(h, "page_number", None),
                    "hits": (cur["hits"] + 1) if cur else 1,
                }
            elif cur:
                cur["hits"] += 1

        selected = sorted(
            ((d, v) for d, v in best.items() if v["score"] >= min_score),
            key=lambda kv: kv[1]["score"],
            reverse=True,
        )[:max_docs]

        # Idempotent: clear existing links for this package first.
        await db.execute(
            delete(PackageDocument).where(PackageDocument.package_id == package.id)
        )

        trade = package.trade_category or "package"
        for doc_id, v in selected:
            db.add(
                PackageDocument(
                    package_id=package.id,
                    document_id=doc_id,
                    relevance_score=round(v["score"], 4),
                    relevance_reason=f"{v['hits']} relevant section(s) for {trade}",
                    excerpt=v["excerpt"],
                    page_ranges=[[v["page"], v["page"]]] if v["page"] else None,
                )
            )
        await db.commit()
        return len(selected)

    async def link_all(self, db: AsyncSession, project_id: int) -> dict:
        """Link documents for every package in a project."""
        packages = (
            await db.execute(
                select(Package).where(Package.project_id == project_id)
            )
        ).scalars().all()
        total = 0
        for package in packages:
            total += await self.link_package(db, package)
        return {"project_id": project_id, "packages": len(packages), "links_created": total}
