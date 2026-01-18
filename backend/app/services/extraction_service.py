"""AI Extraction Service for project summary and checklist generation."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_context
from app.models import Document, Project
from app.models.base import DocumentCategory, DocumentStatus, ProjectStatus
from app.prompts.project_summary import build_summary_prompt, SUMMARY_FIELDS
from app.prompts.checklist import build_checklist_prompt, CHECKLIST_CATEGORIES
from app.services.llm_service import LLMService, LLMProvider
from app.services.vector_store import VectorStoreService

settings = get_settings()


class ExtractionService:
    """Service for AI-powered information extraction.

    Handles:
    - Project summary extraction with evidence citations
    - Requirements checklist generation
    - Document classification
    - Field validation and confidence scoring
    """

    def __init__(self):
        """Initialize extraction service."""
        self.llm = LLMService()
        self.vector_store = VectorStoreService()

    async def extract_project_summary(
        self,
        project_id: int,
        force_refresh: bool = False,
    ) -> dict:
        """Extract structured project summary from tender documents.

        Args:
            project_id: Project ID
            force_refresh: Force re-extraction even if summary exists

        Returns:
            Extracted summary with evidence citations
        """
        async with get_db_context() as db:
            # Get project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Check if summary already exists
            if project.summary and not force_refresh:
                return project.summary

            # Get relevant documents (ITT, Contract, Specs)
            priority_categories = [
                DocumentCategory.ITT,
                DocumentCategory.CONTRACT,
                DocumentCategory.SPECS,
                DocumentCategory.ADDENDUM,
            ]

            documents = await self._get_documents_by_priority(
                db, project_id, priority_categories
            )

            if not documents:
                raise ValueError("No indexed documents found for project")

            # Prepare document context for LLM
            doc_contexts = []
            for doc in documents[:10]:  # Limit to top 10 documents
                content = doc.extracted_text or ""
                # Truncate if too long
                if len(content) > 8000:
                    content = content[:8000] + "\n...[truncated]..."

                doc_contexts.append({
                    "filename": doc.filename,
                    "content": content,
                    "category": doc.category.value if doc.category else "unknown",
                })

            # Build prompt and extract
            prompt = build_summary_prompt(doc_contexts)

            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    task_type="summary_extraction",
                    json_mode=True,
                )

                summary = json.loads(response)

                # Validate and enhance summary
                summary = await self._validate_summary(summary)

                # Update project
                project.summary = summary
                project.status = ProjectStatus.READY
                await db.commit()

                return summary

            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse summary response: {e}")

    async def _get_documents_by_priority(
        self,
        db: AsyncSession,
        project_id: int,
        priority_categories: list[DocumentCategory],
    ) -> list[Document]:
        """Get documents ordered by category priority.

        Args:
            db: Database session
            project_id: Project ID
            priority_categories: Categories in priority order

        Returns:
            List of documents
        """
        # Get all indexed documents
        result = await db.execute(
            select(Document).where(
                Document.project_id == project_id,
                Document.status == DocumentStatus.INDEXED,
            )
        )
        all_docs = list(result.scalars().all())

        # Sort by priority
        def get_priority(doc):
            try:
                return priority_categories.index(doc.category)
            except (ValueError, TypeError):
                return len(priority_categories)

        return sorted(all_docs, key=get_priority)

    async def _validate_summary(self, summary: dict) -> dict:
        """Validate and enhance extracted summary.

        Args:
            summary: Raw extracted summary

        Returns:
            Validated summary with flags
        """
        validated = {}

        for field in SUMMARY_FIELDS:
            field_data = summary.get(field, {})

            if not isinstance(field_data, dict):
                field_data = {"value": field_data, "confidence": 0.5, "evidence": []}

            # Ensure required structure
            validated[field] = {
                "value": field_data.get("value"),
                "confidence": float(field_data.get("confidence", 0.0)),
                "evidence": field_data.get("evidence", []),
                "requires_review": field_data.get("confidence", 0.0) < settings.REVIEW_THRESHOLD,
            }

            # Parse dates if applicable
            if "date" in field or "deadline" in field:
                validated[field] = self._parse_date_field(validated[field])

        return validated

    def _parse_date_field(self, field_data: dict) -> dict:
        """Try to parse date value into ISO format.

        Args:
            field_data: Field data with value

        Returns:
            Field data with parsed date
        """
        value = field_data.get("value")
        if not value or not isinstance(value, str):
            return field_data

        # Common date formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %B %Y",
            "%B %d, %Y",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value.strip(), fmt)
                field_data["value"] = parsed.isoformat()
                field_data["parsed"] = True
                return field_data
            except ValueError:
                continue

        field_data["parsed"] = False
        return field_data

    async def generate_checklist(
        self,
        project_id: int,
        force_refresh: bool = False,
    ) -> list[dict]:
        """Generate requirements checklist from tender documents.

        Args:
            project_id: Project ID
            force_refresh: Force re-generation

        Returns:
            List of requirement items
        """
        async with get_db_context() as db:
            # Get project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Check if checklist exists
            if project.checklist and not force_refresh:
                return project.checklist

            # Get relevant documents
            priority_categories = [
                DocumentCategory.ITT,
                DocumentCategory.CONTRACT,
                DocumentCategory.SPECS,
                DocumentCategory.HSE,
            ]

            documents = await self._get_documents_by_priority(
                db, project_id, priority_categories
            )

            if not documents:
                raise ValueError("No indexed documents found for project")

            # Prepare document context
            doc_contexts = []
            for doc in documents[:8]:  # Limit to 8 documents
                content = doc.extracted_text or ""
                if len(content) > 6000:
                    content = content[:6000] + "\n...[truncated]..."

                doc_contexts.append({
                    "filename": doc.filename,
                    "content": content,
                    "category": doc.category.value if doc.category else "unknown",
                })

            # Build prompt and generate
            prompt = build_checklist_prompt(doc_contexts)

            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    task_type="checklist_generation",
                    json_mode=True,
                )

                result = json.loads(response)
                requirements = result.get("requirements", [])

                # Validate and enhance
                checklist = self._validate_checklist(requirements)

                # Update project
                project.checklist = checklist
                await db.commit()

                return checklist

            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse checklist response: {e}")

    def _validate_checklist(self, requirements: list) -> list[dict]:
        """Validate and standardize checklist items.

        Args:
            requirements: Raw requirements list

        Returns:
            Validated checklist
        """
        validated = []

        for i, req in enumerate(requirements):
            if not isinstance(req, dict):
                continue

            # Standardize category
            category = req.get("category", "GENERAL").upper()
            if category not in CHECKLIST_CATEGORIES:
                category = "GENERAL"

            validated.append({
                "id": req.get("id", i + 1),
                "category": category,
                "requirement": req.get("requirement", ""),
                "description": req.get("description", ""),
                "mandatory": bool(req.get("mandatory", True)),
                "source_document": req.get("source_document"),
                "source_reference": req.get("source_reference"),
                "responsible_party": req.get("responsible_party"),
                "deadline": req.get("deadline"),
                "deliverable": req.get("deliverable"),
                "status": "open",
                "notes": None,
            })

        return validated

    async def classify_document(
        self,
        document_id: int,
    ) -> dict:
        """Classify a document into a category using AI.

        Args:
            document_id: Document ID

        Returns:
            Classification result
        """
        from app.prompts.classification import DOCUMENT_CLASSIFICATION_PROMPT

        async with get_db_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                raise ValueError(f"Document not found: {document_id}")

            content = document.extracted_text or ""
            if len(content) > 2000:
                content = content[:2000]

            prompt = DOCUMENT_CLASSIFICATION_PROMPT.format(
                filename=document.filename,
                content=content,
            )

            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    task_type="classification",
                    json_mode=True,
                )

                result = json.loads(response)

                # Map to DocumentCategory
                category_map = {
                    "ITT": DocumentCategory.ITT,
                    "SPECS": DocumentCategory.SPECS,
                    "BOQ": DocumentCategory.BOQ,
                    "DRAWINGS": DocumentCategory.DRAWINGS,
                    "CONTRACT": DocumentCategory.CONTRACT,
                    "ADDENDUM": DocumentCategory.ADDENDUM,
                    "CORRESPONDENCE": DocumentCategory.CORRESPONDENCE,
                    "SCHEDULE": DocumentCategory.SCHEDULE,
                    "HSE": DocumentCategory.HSE,
                    "GENERAL": DocumentCategory.GENERAL,
                }

                category_str = result.get("category", "GENERAL").upper()
                category = category_map.get(category_str, DocumentCategory.GENERAL)

                # Update document
                document.category = category
                document.category_confidence = float(result.get("confidence", 0.5))
                await db.commit()

                return {
                    "document_id": document_id,
                    "category": category.value,
                    "confidence": result.get("confidence", 0.5),
                    "reasoning": result.get("reasoning", ""),
                }

            except json.JSONDecodeError:
                return {
                    "document_id": document_id,
                    "category": DocumentCategory.GENERAL.value,
                    "confidence": 0.0,
                    "reasoning": "Classification failed",
                }

    async def search_with_context(
        self,
        query: str,
        project_id: int,
        top_k: int = 5,
    ) -> dict:
        """Search documents and provide AI-generated answer with context.

        Args:
            query: User question
            project_id: Project ID
            top_k: Number of chunks to retrieve

        Returns:
            Answer with source citations
        """
        # Search for relevant chunks
        results = await self.vector_store.search(
            query=query,
            limit=top_k,
            filter_conditions={"project_id": project_id},
            min_score=0.5,
        )

        if not results:
            return {
                "answer": "I couldn't find relevant information in the project documents.",
                "sources": [],
                "confidence": 0.0,
            }

        # Build context from search results
        context_parts = []
        sources = []

        for result in results:
            context_parts.append(f"""
Document: {result['metadata'].get('filename', 'Unknown')}
Page: {result['metadata'].get('page_number', 'N/A')}

{result['text']}
""")
            sources.append({
                "document": result['metadata'].get('filename'),
                "page": result['metadata'].get('page_number'),
                "score": result['score'],
            })

        context = "\n---\n".join(context_parts)

        # Generate answer
        prompt = f"""Based on the following document excerpts, answer the question.
If the answer cannot be found in the excerpts, say so clearly.
Always cite which document contains the information.

## Question:
{query}

## Document Excerpts:
{context}

## Instructions:
1. Answer the question based only on the provided excerpts
2. Cite the source document for each piece of information
3. If information is unclear or conflicting, note the ambiguity
4. Be concise but complete

Answer:"""

        try:
            answer = await self.llm.generate(
                prompt=prompt,
                task_type="document_understanding",
            )

            return {
                "answer": answer.strip(),
                "sources": sources,
                "confidence": sum(s["score"] for s in sources) / len(sources),
            }

        except Exception as e:
            return {
                "answer": f"Error generating answer: {str(e)}",
                "sources": sources,
                "confidence": 0.0,
            }

    async def extract_key_dates(
        self,
        project_id: int,
    ) -> list[dict]:
        """Extract all key dates from project documents.

        Args:
            project_id: Project ID

        Returns:
            List of extracted dates
        """
        # Search for date-related content
        date_queries = [
            "submission deadline tender due date",
            "site visit inspection date",
            "clarification deadline queries",
            "award date contract signing",
            "commencement start date",
            "completion end date",
            "milestones schedule",
        ]

        all_dates = []

        for query in date_queries:
            results = await self.vector_store.search(
                query=query,
                limit=3,
                filter_conditions={"project_id": project_id},
                min_score=0.6,
            )

            for result in results:
                # Use LLM to extract dates from the chunk
                prompt = f"""Extract any dates mentioned in this text.
For each date found, provide:
- The date (in YYYY-MM-DD format if possible)
- What the date represents (deadline, milestone, etc.)
- The exact text where it was found

Text:
{result['text']}

Respond with JSON:
{{"dates": [{{"date": "YYYY-MM-DD or original text", "type": "what it represents", "context": "surrounding text"}}]}}"""

                try:
                    response = await self.llm.generate(
                        prompt=prompt,
                        task_type="entity_extraction",
                        json_mode=True,
                    )

                    data = json.loads(response)
                    for date_info in data.get("dates", []):
                        date_info["source_document"] = result['metadata'].get('filename')
                        date_info["source_page"] = result['metadata'].get('page_number')
                        all_dates.append(date_info)

                except (json.JSONDecodeError, Exception):
                    continue

        # Deduplicate by date value
        seen = set()
        unique_dates = []
        for d in all_dates:
            key = (d.get("date"), d.get("type"))
            if key not in seen:
                seen.add(key)
                unique_dates.append(d)

        return unique_dates
