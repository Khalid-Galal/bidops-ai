"""AI offer-data extraction + compliance analysis behind an injectable boundary.

The real GeminiService is resolved lazily from configured keys; when no key is
available _resolve_llm() returns None and the public methods raise
LLMUnavailable (the API maps that to 503). The LLM dependency is injectable so
the parse+map logic is testable without a key (mirrors DocumentLinker).
"""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import SupplierOffer
from app.schemas.offer import ComplianceAnalysis, OfferExtraction
from app.services.parsing.base import get_parser_for_file

logger = logging.getLogger(__name__)

_MAX_FILE_CHARS = 10000
_MAX_TOTAL_CHARS = 30000

_EXTRACTION_PROMPT = """You are extracting commercial data from a supplier's offer for package "{package_name}".

Required BOQ items (for context):
{items}

Offer documents:
{content}

Extract the total price, currency, VAT inclusion, validity (days), payment terms,
delivery time (weeks), any exclusions, any deviations, and priced line items.

INSTRUCTIONS:
1. Copy values EXACTLY as they appear in the source document -- do NOT convert
   units, currencies, or reformat dates/numbers.
2. If a field is not explicitly stated in the documents, set it to null. NEVER
   fabricate or infer a value that is not written in the offer.
3. Currency: capture the currency code or symbol exactly as printed (e.g. USD,
   EGP, SAR, $, "L.E."). If the price is a bare number with no currency stated,
   leave currency null rather than guessing.
4. VAT: only set vat_included to true/false when the offer explicitly states
   whether VAT/tax is included or excluded/additional (e.g. "prices include
   VAT", "VAT not included", "plus 14% VAT"). If VAT is not mentioned at all,
   leave vat_included null.
5. If the offer documents are in Arabic (or mixed Arabic/English), extract
   values from the Arabic text directly -- do NOT translate descriptions,
   payment terms, or exclusions/deviations; keep them as verbatim quotes in
   the source language.
"""

_COMPLIANCE_PROMPT = """Assess this supplier offer against the tender requirements for package "{package_name}".

Requirements:
{requirements}

Offer summary:
{offer}

Decide overall_compliance (COMPLIANT / NON_COMPLIANT / PARTIAL), a 0-100
compliance_score, any missing_items, deviations, and clarifications_needed.

INSTRUCTIONS:
1. Base the assessment only on what is explicitly stated in the requirements
   and offer summary above -- NEVER fabricate or infer missing information.
2. If a requirement is not addressed by the offer at all, list it in
   missing_items rather than guessing compliance.
3. If the offer text includes Arabic content, keep any quoted requirement or
   deviation text verbatim in its original language -- do NOT translate it.
4. Set overall_compliance to UNKNOWN only if there is not enough information
   in the requirements or offer summary to make a determination.
"""


class LLMUnavailable(RuntimeError):
    """Raised when no Gemini key is configured for AI extraction/compliance."""


class OfferExtractor:
    def __init__(self, llm_service=None) -> None:
        self._injected = llm_service

    def _resolve_llm(self):
        if self._injected is not None:
            return self._injected
        from app.config import get_settings
        from app.services.llm.gemini_service import GeminiService

        settings = get_settings()
        keys = settings.gemini_key_list()
        if not keys:
            return None
        return GeminiService(api_keys=keys, model=settings.gemini_model)

    async def _offer_text(self, offer: SupplierOffer) -> str:
        chunks: list[str] = []
        for file_path in offer.file_paths or []:
            try:
                parser = get_parser_for_file(file_path)
                parsed = await parser.parse(file_path)
                chunks.append((parsed.full_text or "")[:_MAX_FILE_CHARS])
            except Exception as exc:  # noqa: BLE001 - a bad file should not abort extraction
                logger.warning("Failed to parse offer file %s: %s", file_path, exc)
        return "\n\n---\n\n".join(chunks)[:_MAX_TOTAL_CHARS]

    async def extract_offer(self, db: AsyncSession, offer_id: int) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        llm = self._resolve_llm()
        if llm is None:
            raise LLMUnavailable("No Gemini API key configured for offer extraction")

        package = await db.get(Package, offer.package_id)
        items = (
            await db.execute(
                select(BOQItem.line_number, BOQItem.description, BOQItem.unit)
                .where(BOQItem.package_id == offer.package_id)
                .order_by(BOQItem.client_row_index)
                .limit(20)
            )
        ).all()
        items_text = "\n".join(
            f"- {ln}: {(desc or '')[:100]} ({unit or ''})" for ln, desc, unit in items
        )
        prompt = _EXTRACTION_PROMPT.format(
            package_name=package.name if package else "",
            items=items_text,
            content=await self._offer_text(offer),
        )
        result: OfferExtraction = await asyncio.to_thread(
            llm.extract, prompt=prompt, response_model=OfferExtraction
        )

        offer.total_price = result.total_price
        offer.currency = result.currency
        offer.vat_included = result.vat_included
        offer.validity_days = result.validity_days
        offer.payment_terms = result.payment_terms
        offer.delivery_weeks = result.delivery_weeks
        offer.exclusions = result.exclusions
        offer.deviations = result.deviations
        offer.line_items = [li.model_dump() for li in result.line_items]
        offer.status = OfferStatus.UNDER_REVIEW.value
        await db.commit()
        return result.model_dump()

    async def check_compliance(self, db: AsyncSession, offer_id: int) -> dict:
        offer = await db.get(SupplierOffer, offer_id)
        if offer is None:
            raise ValueError(f"Offer {offer_id} not found")
        llm = self._resolve_llm()
        if llm is None:
            raise LLMUnavailable("No Gemini API key configured for compliance check")

        package = await db.get(Package, offer.package_id)
        project = await db.get(Project, package.project_id) if package else None
        requirements = self._checklist_requirements(project)
        boq_items = (
            await db.execute(
                select(BOQItem.description)
                .where(BOQItem.package_id == offer.package_id)
                .order_by(BOQItem.client_row_index)
                .limit(30)
            )
        ).scalars().all()
        requirements += [f"- BOQ Item: {(d or '')[:100]}" for d in boq_items]
        offer_summary = (
            f"Total Price: {offer.total_price} {offer.currency or ''}\n"
            f"Payment Terms: {offer.payment_terms or 'n/a'}\n"
            f"Delivery: {offer.delivery_weeks or 'n/a'} weeks\n"
            f"Validity: {offer.validity_days or 'n/a'} days\n"
            f"Exclusions: {offer.exclusions or []}\n"
            f"Line items provided: {len(offer.line_items or [])}"
        )
        prompt = _COMPLIANCE_PROMPT.format(
            package_name=package.name if package else "",
            requirements="\n".join(requirements[:50]) or "(none provided)",
            offer=offer_summary,
        )
        result: ComplianceAnalysis = await asyncio.to_thread(
            llm.extract, prompt=prompt, response_model=ComplianceAnalysis
        )

        offer.compliance_analysis = result.model_dump()
        offer.missing_items = result.missing_items
        offer.deviations = result.deviations or offer.deviations
        offer.clarifications_needed = result.clarifications_needed
        verdict = (result.overall_compliance or "").upper()
        if verdict == "COMPLIANT":
            offer.status = OfferStatus.COMPLIANT.value
        elif verdict == "NON_COMPLIANT":
            offer.status = OfferStatus.NON_COMPLIANT.value
        else:
            offer.status = OfferStatus.UNDER_REVIEW.value
        await db.commit()
        return result.model_dump()

    @staticmethod
    def _checklist_requirements(project: Project | None) -> list[str]:
        if project is None or not project.checklist_json:
            return []
        try:
            data = json.loads(project.checklist_json)
        except (ValueError, TypeError):
            return []
        out: list[str] = []
        for key in ("requirements", "submission_documents", "eligibility_criteria"):
            for req in data.get(key, []) or []:
                text = req.get("requirement") if isinstance(req, dict) else None
                if text:
                    out.append(f"- {text}")
        return out
