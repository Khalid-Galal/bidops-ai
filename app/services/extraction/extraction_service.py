"""Orchestrates per-field retrieval, LLM extraction, and citation verification.

For each of the 13 project summary fields, the ExtractionService:
1. Retrieves relevant chunks from hybrid search using field-specific queries.
2. Builds labeled context for LLM attribution.
3. Extracts structured data via GeminiService with LLMExtractedField schema.
4. Verifies citations and computes confidence via CitationVerifier.
5. Stores verified ExtractedField results in a ProjectSummary.

The extract_and_persist() method additionally saves results to the database
and tracks extraction status (in_progress -> completed/failed).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from app.schemas.extraction import (
    Citation,
    ExtractedField,
    LLMExtractedField,
    ProjectSummary,
)
from app.services.extraction.field_definitions import SUMMARY_FIELDS, FieldDefinition
from app.services.llm.context_builder import build_extraction_prompt, build_labeled_context

if TYPE_CHECKING:
    from app.services.extraction.citation_verifier import CitationVerifier
    from app.services.llm.gemini_service import GeminiService
    from app.services.search.hybrid_search import HybridSearchService, SearchResult

logger = logging.getLogger(__name__)


class ExtractionService:
    """Orchestrates per-field extraction with retrieval, LLM, and NLI verification.

    Args:
        search_service: HybridSearchService for per-field chunk retrieval.
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
        logger.info("ExtractionService initialized")

    async def extract_project_summary(self, project_id: int) -> ProjectSummary:
        """Extract complete project summary from indexed documents using per-field retrieval and LLM extraction.

        For each of the 13 summary fields:
        1. Retrieve relevant chunks via hybrid search.
        2. Build labeled context with source metadata.
        3. Extract via Gemini LLM with LLMExtractedField schema.
        4. Verify citations via NLI cross-encoder.
        5. Store verified result.

        Args:
            project_id: Database ID of the project to extract from.

        Returns:
            ProjectSummary with all 13 fields populated.
        """
        start_time = time.time()
        results: dict[str, ExtractedField] = {}

        for i, field_def in enumerate(SUMMARY_FIELDS):
            # 1. Retrieve relevant chunks
            chunks: list[SearchResult] = self._search_service.search(
                project_id=project_id,
                query=field_def.query,
                top_k=field_def.top_k,
                mode="hybrid",
            )

            if not chunks:
                logger.info(
                    "No chunks found for field %s, creating empty field",
                    field_def.name,
                )
                results[field_def.name] = ExtractedField(
                    value=None,
                    confidence=0.0,
                    confidence_level="low",
                    requires_review=True,
                )
                continue

            # 2. Build labeled context
            context = build_labeled_context(chunks)

            # 3. Build extraction prompt
            prompt = build_extraction_prompt(field_def, context)

            # 4. Extract via LLM
            try:
                llm_result: LLMExtractedField = await asyncio.to_thread(
                    self._llm_service.extract,
                    prompt=prompt,
                    response_model=LLMExtractedField,
                )
            except Exception:
                logger.warning(
                    "LLM extraction failed for field %s, creating empty field",
                    field_def.name,
                    exc_info=True,
                )
                results[field_def.name] = ExtractedField(
                    value=None,
                    confidence=0.0,
                    confidence_level="low",
                    requires_review=True,
                )
                continue

            # 5. Convert LLMExtractedField to ExtractedField
            extracted_field = ExtractedField(
                value=llm_result.value,
                confidence=llm_result.confidence,
                confidence_level="low",
                citations=llm_result.citations,
                reasoning=llm_result.reasoning,
                requires_review=True,
            )

            # 6. Verify citations via NLI
            retrieval_scores = [chunk.score for chunk in chunks]
            verified_field = self._citation_verifier.verify_field(
                field=extracted_field,
                source_chunks=chunks,
                retrieval_scores=retrieval_scores,
            )

            # 7. Store result
            results[field_def.name] = verified_field

            value_preview = (
                verified_field.value[:60] + "..."
                if verified_field.value and len(verified_field.value) > 60
                else verified_field.value
            )
            logger.info(
                "Extracted %s: value='%s', confidence=%s",
                field_def.name,
                value_preview or "None",
                verified_field.confidence_level,
            )

            # Small delay between LLM calls to avoid rate limiting
            if i < len(SUMMARY_FIELDS) - 1:
                await asyncio.sleep(0.5)

        elapsed = time.time() - start_time
        logger.info(
            "Extraction complete for project %d: %d fields in %.1fs",
            project_id,
            len(results),
            elapsed,
        )

        return ProjectSummary(**results)

    async def extract_and_persist(self, project_id: int) -> ProjectSummary:
        """Extract project summary and persist to database.

        Updates the project's extraction_status through the lifecycle:
        None -> "in_progress" -> "completed" (or "failed").

        Args:
            project_id: Database ID of the project.

        Returns:
            The extracted ProjectSummary.

        Raises:
            ValueError: If the project does not exist.
            Exception: Re-raised after setting status to "failed".
        """
        from app.database import async_session_factory
        from app.models.project import Project

        # Set extraction status to in_progress
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                raise ValueError(f"Project {project_id} not found")
            project.extraction_status = "in_progress"
            await session.commit()

        try:
            summary = await self.extract_project_summary(project_id)

            # Persist results
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                project.summary_json = summary.model_dump_json()
                project.extraction_status = "completed"
                await session.commit()

            return summary

        except Exception:
            logger.exception(
                "Extraction failed for project %d", project_id
            )
            # Update status to failed
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                if project:
                    project.extraction_status = "failed"
                    await session.commit()
            raise
