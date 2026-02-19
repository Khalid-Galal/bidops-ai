"""Pydantic models for structured extraction output with embedded citations.

Defines the schema hierarchy for project summary extraction:
- Citation: Links an extracted value to its source document and page.
- LLMExtractedField: Schema passed to the LLM (without post-processing fields).
- ExtractedField: Full field with confidence_level and requires_review (set post-extraction).
- ProjectSummary: All 13 extraction fields as ExtractedField instances.
- ExtractionResponse: API response wrapper with status and metrics.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A citation linking an extracted value to its source document."""

    document_name: str = Field(
        description="Filename of the source document"
    )
    page_number: int = Field(
        ge=1,
        description="1-based page number where the value was found",
    )
    quote: str = Field(
        min_length=1,
        description="Exact verbatim quote from the source supporting this value",
    )


class LLMExtractedField(BaseModel):
    """Schema passed to the LLM for extraction (without post-processing fields).

    The LLM fills value, confidence, citations, and reasoning.
    Fields like confidence_level and requires_review are computed
    after NLI verification in the extraction pipeline.
    """

    value: str | None = Field(
        default=None,
        description="The extracted value, or null if not found in documents",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence from 0.0 to 1.0",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations supporting this extraction",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of extraction logic",
    )


class ExtractedField(BaseModel):
    """A single extracted field with citation, confidence, and review flag.

    After LLM extraction, the pipeline sets confidence_level and
    requires_review based on NLI verification and confidence thresholds.
    """

    value: str | None = Field(
        default=None,
        description="The extracted value, or null if not found in documents",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0",
    )
    confidence_level: str = Field(
        default="low",
        description="Human-readable confidence: high, medium, or low",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations supporting this extraction",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of how the value was determined",
    )
    requires_review: bool = Field(
        default=True,
        description="Whether this extraction needs human review",
    )


class ProjectSummary(BaseModel):
    """Complete project summary with all 13 extracted fields."""

    project_name: ExtractedField
    project_owner: ExtractedField
    location: ExtractedField
    submission_deadline: ExtractedField
    bid_validity_period: ExtractedField
    pre_bid_meeting_date: ExtractedField
    scope_of_work: ExtractedField
    contract_type: ExtractedField
    tender_bond: ExtractedField
    advance_payment: ExtractedField
    retention_percentage: ExtractedField
    payment_terms: ExtractedField
    stakeholders: ExtractedField


class ExtractionResponse(BaseModel):
    """API response wrapper for extraction results."""

    project_id: int
    status: str = Field(
        description='Extraction status: "completed", "in_progress", or "failed"'
    )
    summary: ProjectSummary | None = None
    extraction_time_seconds: float | None = None
    fields_extracted: int = Field(
        default=0,
        description="Count of non-null extracted fields",
    )
    fields_requiring_review: int = Field(
        default=0,
        description="Count of fields with requires_review=True",
    )
