"""Content-hash dedup + filename revision chains + classification.

analyze() is idempotent: it resets ONLY auto-applied marks (supersede_reason
starting with "auto:") and re-derives them; manual marks survive and manually
superseded documents are never selected as chain keepers. Deterministic — no
LLM. True cross-document addenda judgment (e.g. "Addendum 2 replaces section 5
of the ITT") is a human call: use mark_superseded for it.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.rules.rules_service import RulesService
from app.services.versioning.doc_classifier import classify_document

# Filename version tokens, tried in order. Each yields (rank, label).
_VERSION_PATTERNS = (
    ("rev", re.compile(r"(?:^|[\s_\-.])rev(?:ision)?[\s_\-.]*([a-z]|\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
    ("v", re.compile(r"(?:^|[\s_\-.])v(?:er(?:sion)?)?[\s_\-.]*(\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
    ("issue", re.compile(r"(?:^|[\s_\-.])issue[\s_\-.]*(\d{1,3})(?=[\s_\-.)(]|$)", re.I)),
)


def _normalize_base(stem: str) -> str:
    return re.sub(r"[^\w]+", "_", stem.lower()).strip("_")


def parse_version(filename: str) -> tuple[str, int, str | None]:
    """Return (base_key, rank, label). rank 0 / label None when no token found.

    The base_key strips the version token so 'Spec_RevA.pdf' and
    'Spec rev.B.pdf' share a base and form one revision chain.
    """
    stem = Path(filename).stem
    for kind, pattern in _VERSION_PATTERNS:
        m = pattern.search(stem)
        if m:
            token = m.group(1)
            rank = (ord(token.lower()) - ord("a") + 1) if token.isalpha() else int(token)
            base = stem[: m.start()] + " " + stem[m.end():]
            return _normalize_base(base), rank, f"{kind} {token.upper()}"
    return _normalize_base(stem), 0, None


def _hash_document(doc: Document) -> str | None:
    path = Path(doc.file_path)
    if path.exists() and path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if doc.extracted_text:
        return hashlib.sha256(doc.extracted_text.encode("utf-8")).hexdigest()
    return None


class VersioningService:
    def __init__(self, rules_service: RulesService | None = None) -> None:
        self._rules_service = rules_service or RulesService()

    async def analyze(self, db: AsyncSession, project_id: int) -> dict:
        rules = self._rules_service.load()

        # Reset ONLY auto marks; manual marks survive re-analysis.
        await db.execute(
            update(Document)
            .where(
                Document.project_id == project_id,
                Document.supersede_reason.like("auto:%"),
            )
            .values(is_superseded=False, superseded_by_id=None, supersede_reason=None)
        )

        docs = list(
            (
                await db.execute(
                    select(Document)
                    .where(Document.project_id == project_id)
                    .order_by(Document.id)
                )
            ).scalars().all()
        )

        # 1) Classify everything + ensure hashes + version labels.
        by_category: dict[str, int] = defaultdict(int)
        for doc in docs:
            category, _conf = classify_document(doc.filename, doc.extracted_text, rules)
            doc.category = category
            by_category[category] += 1
            if not doc.content_hash:
                doc.content_hash = _hash_document(doc)
            _base, _rank, label = parse_version(doc.filename)
            doc.version_label = label

        manual_superseded = {
            d.id for d in docs
            if d.is_superseded and not (d.supersede_reason or "").startswith("auto:")
        }
        candidates = [d for d in docs if d.id not in manual_superseded]

        # 2) Exact duplicates by content hash — keep the EARLIEST copy.
        duplicates = 0
        groups: dict[str, list[Document]] = defaultdict(list)
        for doc in candidates:
            if doc.content_hash:
                groups[doc.content_hash].append(doc)
        duplicate_ids: set[int] = set()
        for group in groups.values():
            if len(group) < 2:
                continue
            keeper = min(group, key=lambda d: d.id)
            for doc in group:
                if doc.id == keeper.id:
                    continue
                doc.is_superseded = True
                doc.superseded_by_id = keeper.id
                doc.supersede_reason = f"auto:duplicate of #{keeper.id}"
                duplicate_ids.add(doc.id)
                duplicates += 1

        # 3) Revision chains by (base_key, file_type) — newest rank wins.
        superseded = 0
        chains: dict[tuple[str, str], list[tuple[Document, int]]] = defaultdict(list)
        for doc in candidates:
            if doc.id in duplicate_ids:
                continue
            base, rank, _label = parse_version(doc.filename)
            chains[(base, doc.file_type)].append((doc, rank))
        for members in chains.values():
            if len(members) < 2 or not any(rank > 0 for _d, rank in members):
                continue  # need 2+ docs and at least one explicit version token
            # id encodes upload order (created_at can be None pre-commit and
            # mixing datetime/int in a sort key raises TypeError).
            members.sort(key=lambda dr: (dr[1], dr[0].id))
            keeper = members[-1][0]
            for doc, _rank in members[:-1]:
                doc.is_superseded = True
                doc.superseded_by_id = keeper.id
                doc.supersede_reason = f"auto:superseded by #{keeper.id} (newer revision)"
                superseded += 1

        await db.commit()
        return {
            "project_id": project_id,
            "documents": len(docs),
            "duplicates": duplicates,
            "superseded": superseded,
            "by_category": dict(by_category),
        }

    async def mark_superseded(
        self,
        db: AsyncSession,
        document_id: int,
        *,
        superseded_by_id: int | None,
        reason: str,
    ) -> Document | None:
        doc = await db.get(Document, document_id)
        if doc is None:
            return None
        doc.is_superseded = True
        doc.superseded_by_id = superseded_by_id
        doc.supersede_reason = reason or "manually superseded"
        await db.commit()
        await db.refresh(doc)
        return doc

    async def unmark_superseded(self, db: AsyncSession, document_id: int) -> Document | None:
        doc = await db.get(Document, document_id)
        if doc is None:
            return None
        doc.is_superseded = False
        doc.superseded_by_id = None
        doc.supersede_reason = None
        await db.commit()
        await db.refresh(doc)
        return doc
