"""Orchestrates category-based requirements checklist extraction.

For each of the 6 requirement categories, the ChecklistService:
1. Retrieves relevant chunks via multi-query hybrid search (merged, deduplicated).
2. Builds labeled context for LLM attribution.
3. Extracts a list of RequirementItems via GeminiService with CategoryExtractionResponse.
4. Verifies each requirement's citation via NLI cross-encoder.
5. Computes three-signal confidence (NLI + retrieval + LLM).
6. Deduplicates semantically similar requirements across categories.
7. Assembles the final RequirementsChecklist grouped by type.

The extract_and_persist_checklist() method additionally saves results to the
database and tracks checklist_status (in_progress -> completed/failed).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from app.schemas.checklist import (
    CategoryExtractionResponse,
    RequirementsChecklist,
    VerifiedRequirement,
)
from app.schemas.extraction import Citation
from app.services.extraction.checklist_definitions import CHECKLIST_CATEGORIES
from app.services.llm.context_builder import (
    build_checklist_extraction_prompt,
    build_labeled_context,
)

if TYPE_CHECKING:
    from app.services.extraction.checklist_definitions import CategoryDefinition
    from app.services.extraction.citation_verifier import CitationVerifier
    from app.services.llm.gemini_service import GeminiService
    from app.services.search.hybrid_search import HybridSearchService, SearchResult

logger = logging.getLogger(__name__)

# Cross-category dedup precedence. submission_documents and eligibility are the
# checklist's dedicated buckets -- a document that must be submitted with the bid
# (or an eligibility condition) belongs in its own tab even when it is a
# near-duplicate of a technical/commercial/legal/hse item, so those categories
# win a cross-category duplicate pair regardless of confidence.
_DEDUP_CATEGORY_PRIORITY = {"submission_documents": 2, "eligibility": 1}


def _dedup_priority(category: str) -> int:
    """Return the cross-category dedup precedence for a requirement category."""
    return _DEDUP_CATEGORY_PRIORITY.get(category, 0)


class ChecklistService:
    """Orchestrates per-category extraction with retrieval, LLM, NLI, and deduplication.

    Args:
        search_service: HybridSearchService for multi-query chunk retrieval.
        llm_service: GeminiService for structured LLM extraction.
        citation_verifier: CitationVerifier for NLI-based citation verification.
    """

    def __init__(
        self,
        search_service: HybridSearchService,
        llm_service: GeminiService,
        citation_verifier: CitationVerifier,
    ) -> None:
        self._search_service = search_service
        self._llm_service = llm_service
        self._citation_verifier = citation_verifier
        logger.info("ChecklistService initialized")

    # ------------------------------------------------------------------
    # Multi-query retrieval
    # ------------------------------------------------------------------

    def _retrieve_category_chunks(
        self, project_id: int, category: CategoryDefinition
    ) -> list[SearchResult]:
        """Retrieve and deduplicate chunks across multiple queries for one category.

        For each query in the category definition, runs hybrid search and
        merges results. Duplicate chunks (same chunk_id) are kept only once
        (first occurrence wins). Final list is sorted by score descending
        and capped at category.max_context_chunks.

        Args:
            project_id: Database ID of the project to search.
            category: The category definition with queries and retrieval params.

        Returns:
            Deduplicated, score-sorted list of SearchResult objects.
        """
        seen_chunk_ids: set[str] = set()
        all_chunks: list[SearchResult] = []

        for query in category.queries:
            results: list[SearchResult] = self._search_service.search(
                project_id=project_id,
                query=query,
                top_k=category.top_k_per_query,
                mode="hybrid",
            )
            for chunk in results:
                if chunk.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk.chunk_id)
                    all_chunks.append(chunk)

        # Sort by score descending, cap at max_context_chunks
        all_chunks.sort(key=lambda c: c.score, reverse=True)
        return all_chunks[: category.max_context_chunks]

    # ------------------------------------------------------------------
    # Per-category extraction + NLI verification
    # ------------------------------------------------------------------

    async def _extract_category(
        self, project_id: int, category: CategoryDefinition
    ) -> list[VerifiedRequirement]:
        """Extract and verify requirements for one category.

        Pipeline per category:
        1. Multi-query retrieval -> deduplicated chunks.
        2. Build labeled context for LLM attribution.
        3. LLM extraction via Gemini with CategoryExtractionResponse.
        4. NLI verification per requirement item.
        5. Three-signal confidence scoring.

        Individual category failures produce an empty list (graceful degradation).

        Args:
            project_id: Database ID of the project.
            category: The category definition to extract.

        Returns:
            List of VerifiedRequirement objects for this category.
        """
        # 1. Retrieve chunks
        chunks = self._retrieve_category_chunks(project_id, category)
        if not chunks:
            logger.info(
                "No chunks found for category %s, skipping",
                category.display_name,
            )
            return []

        # 2. Build context and prompt
        context = build_labeled_context(chunks)
        prompt = build_checklist_extraction_prompt(category, context)

        # 3. LLM extraction
        try:
            response: CategoryExtractionResponse = await asyncio.to_thread(
                self._llm_service.extract,
                prompt=prompt,
                response_model=CategoryExtractionResponse,
            )
        except Exception:
            logger.warning(
                "LLM extraction failed for category %s, returning empty list",
                category.display_name,
                exc_info=True,
            )
            return []

        # 4. Verify each requirement item
        verified: list[VerifiedRequirement] = []
        for item in response.items:
            # Build citation from the LLM-extracted item
            citation = Citation(
                document_name=item.source_document,
                page_number=item.page_number,
                quote=item.quote,
            )

            # Find matching source chunk via the single shared matcher so both
            # extraction paths (summary + checklist) behave identically.
            source: SearchResult | None = self._citation_verifier._find_source_chunk(
                citation, chunks
            )

            # NLI verification
            if source is not None:
                nli_score = self._citation_verifier.verify_citation(
                    claim=item.quote, source_text=source.text
                )
                retrieval_score = source.score
            else:
                nli_score = 0.0
                retrieval_score = 0.5

            # Three-signal confidence
            score, level, requires_review = self._citation_verifier.calculate_confidence(
                llm_confidence=item.confidence,
                retrieval_score=retrieval_score,
                nli_entailment_score=nli_score,
                has_verified_citation=nli_score >= 0.3,
            )

            verified.append(
                VerifiedRequirement(
                    requirement=item.requirement,
                    description=item.description,
                    category=category.name,
                    is_mandatory=item.is_mandatory,
                    citation=citation,
                    nli_score=nli_score,
                    confidence=score,
                    confidence_level=level,
                    requires_review=requires_review,
                )
            )

        return verified

    # ------------------------------------------------------------------
    # Semantic deduplication
    # ------------------------------------------------------------------

    def _deduplicate(
        self, requirements: list[VerifiedRequirement]
    ) -> list[VerifiedRequirement]:
        """Remove near-duplicate requirements across categories using cosine similarity.

        Encodes all requirement texts with the project's sentence-transformer
        model and removes items whose cosine similarity >= 0.9 with a
        higher-confidence item.

        If the embedding model is unavailable, returns all items unchanged.

        Args:
            requirements: All verified requirements from all categories.

        Returns:
            Deduplicated list of VerifiedRequirement objects.
        """
        if len(requirements) <= 1:
            return requirements

        # Get sentence-transformer model for encoding
        try:
            model = self._search_service._embedding_service._get_model()
        except Exception:
            logger.warning(
                "Embedding model unavailable for deduplication, skipping"
            )
            return requirements

        # Encode all requirement texts
        texts = [r.requirement for r in requirements]
        embeddings = model.encode(texts)

        # Mark duplicates (lower-confidence item in each duplicate pair)
        duplicate_indices: set[int] = set()
        n = len(requirements)
        for i in range(n):
            if i in duplicate_indices:
                continue
            for j in range(i + 1, n):
                if j in duplicate_indices:
                    continue
                # Cosine similarity
                a = embeddings[i]
                b = embeddings[j]
                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)
                if norm_a == 0 or norm_b == 0:
                    continue
                similarity = float(np.dot(a, b) / (norm_a * norm_b))

                if similarity >= 0.9:
                    # Decide which copy survives. A submission_documents /
                    # eligibility item wins the pair outright (never starve the
                    # dedicated buckets); otherwise the higher-confidence item
                    # wins, keeping the earlier one on exact ties.
                    pi = _dedup_priority(requirements[i].category)
                    pj = _dedup_priority(requirements[j].category)
                    if pi != pj:
                        keep_i = pi > pj
                    else:
                        keep_i = requirements[i].confidence >= requirements[j].confidence
                    if keep_i:
                        duplicate_indices.add(j)
                    else:
                        duplicate_indices.add(i)
                        break  # i is now a duplicate, stop comparing it

        unique = [r for idx, r in enumerate(requirements) if idx not in duplicate_indices]
        removed = len(requirements) - len(unique)
        if removed > 0:
            logger.info(
                "Deduplication removed %d near-duplicate requirements (%d -> %d)",
                removed,
                len(requirements),
                len(unique),
            )
        return unique

    # ------------------------------------------------------------------
    # Checklist assembly
    # ------------------------------------------------------------------

    def _assemble_checklist(
        self, requirements: list[VerifiedRequirement]
    ) -> RequirementsChecklist:
        """Group verified requirements into the final checklist structure.

        Splits requirements into three groups:
        - submission_documents: category == "submission_documents"
        - eligibility_criteria: category == "eligibility"
        - requirements: everything else (technical, commercial, legal, hse)

        Args:
            requirements: Deduplicated list of all verified requirements.

        Returns:
            Assembled RequirementsChecklist with counts and category list.
        """
        general: list[VerifiedRequirement] = []
        submission_docs: list[VerifiedRequirement] = []
        eligibility: list[VerifiedRequirement] = []

        for req in requirements:
            if req.category == "submission_documents":
                submission_docs.append(req)
            elif req.category == "eligibility":
                eligibility.append(req)
            else:
                general.append(req)

        total_count = len(requirements)
        mandatory_count = sum(1 for r in requirements if r.is_mandatory)
        categories_extracted = sorted({r.category for r in requirements})

        return RequirementsChecklist(
            requirements=general,
            submission_documents=submission_docs,
            eligibility_criteria=eligibility,
            total_count=total_count,
            mandatory_count=mandatory_count,
            categories_extracted=categories_extracted,
        )

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    async def extract_checklist(self, project_id: int) -> RequirementsChecklist:
        """Extract complete requirements checklist from indexed documents.

        Orchestrates the full pipeline:
        1. Per-category multi-query retrieval + LLM extraction + NLI verification.
        2. Semantic deduplication across all categories.
        3. Checklist assembly with grouping and counts.

        Args:
            project_id: Database ID of the project to extract from.

        Returns:
            Complete RequirementsChecklist with verified, deduplicated requirements.
        """
        start_time = time.time()
        all_requirements: list[VerifiedRequirement] = []

        for i, category in enumerate(CHECKLIST_CATEGORIES):
            category_results = await self._extract_category(project_id, category)
            all_requirements.extend(category_results)
            logger.info(
                "Extracted %d %s requirements",
                len(category_results),
                category.display_name,
            )

            # Rate limiting between categories
            if i < len(CHECKLIST_CATEGORIES) - 1:
                await asyncio.sleep(0.5)

        # Deduplicate across categories
        unique = self._deduplicate(all_requirements)

        # Assemble final checklist
        checklist = self._assemble_checklist(unique)

        elapsed = time.time() - start_time
        logger.info(
            "Checklist extraction complete: %d requirements in %.1fs",
            checklist.total_count,
            elapsed,
        )

        return checklist

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def extract_and_persist_checklist(
        self, project_id: int
    ) -> RequirementsChecklist:
        """Extract requirements checklist and persist to database.

        Updates the project's checklist_status through the lifecycle:
        None -> "in_progress" -> "completed" (or "failed").

        Args:
            project_id: Database ID of the project.

        Returns:
            The extracted RequirementsChecklist.

        Raises:
            ValueError: If the project does not exist.
            Exception: Re-raised after setting status to "failed".
        """
        from app.database import async_session_factory
        from app.models.project import Project

        # Set checklist status to in_progress
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                raise ValueError(f"Project {project_id} not found")
            project.checklist_status = "in_progress"
            await session.commit()

        try:
            checklist = await self.extract_checklist(project_id)

            # Persist results
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                project.checklist_json = checklist.model_dump_json()
                project.checklist_status = "completed"
                await session.commit()

            return checklist

        except Exception:
            logger.exception(
                "Checklist extraction failed for project %d", project_id
            )
            # Update status to failed
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                if project:
                    project.checklist_status = "failed"
                    await session.commit()
            raise
