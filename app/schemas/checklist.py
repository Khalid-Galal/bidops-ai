"""Pydantic models for requirements checklist extraction with embedded citations.

Defines the schema hierarchy for category-based requirements extraction:
- RequirementItem: Schema passed to the LLM via instructor for extracting a single requirement.
- CategoryExtractionResponse: Wrapper model for instructor extraction (list of RequirementItem).
- VerifiedRequirement: Post-NLI verified requirement with category, citation, and confidence.
- RequirementsChecklist: Complete assembled checklist grouping requirements by type.
- ChecklistResponse: API response wrapper with status, counts, and optional checklist data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.extraction import Citation


class RequirementItem(BaseModel):
    """A single requirement extracted by the LLM from tender documents.

    This schema is passed to the LLM via instructor for structured extraction.
    Each item represents one requirement, obligation, or condition found in
    the source documents.
    """

    requirement: str = Field(
        description="Clear, concise statement of the requirement or obligation",
    )
    description: str = Field(
        default="",
        description="Additional context, details, or specific criteria for this requirement",
    )
    is_mandatory: bool = Field(
        description=(
            "True for shall/must/required/mandatory language, "
            "False for should/may/recommended language. "
            "Default to True for ambiguous cases."
        ),
    )
    source_document: str = Field(
        description="Filename of the source document",
    )
    page_number: int = Field(
        ge=1,
        description="1-based page number where the requirement was found",
    )
    quote: str = Field(
        min_length=1,
        description="Exact verbatim quote from source supporting this requirement",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM self-assessed confidence from 0.0 to 1.0",
    )


class CategoryExtractionResponse(BaseModel):
    """Wrapper model for instructor extraction of one category of requirements.

    Uses a wrapper model instead of Iterable[RequirementItem] because the
    wrapper pattern is more reliable with Gemini structured output.
    """

    items: list[RequirementItem] = Field(
        default_factory=list,
        description="All requirements found for this category",
    )
    reasoning: str = Field(
        default="",
        description="Brief summary of extraction approach and findings",
    )


class VerifiedRequirement(BaseModel):
    """A requirement after NLI citation verification and confidence scoring.

    Created by the checklist service after verifying each RequirementItem's
    citation against source chunks using the NLI cross-encoder.
    """

    requirement: str = Field(
        description="Clear, concise statement of the requirement",
    )
    description: str = Field(
        default="",
        description="Additional context or specific criteria",
    )
    category: str = Field(
        description="Requirement category (e.g., technical, commercial, legal, hse)",
    )
    is_mandatory: bool = Field(
        description="Whether the requirement uses mandatory language",
    )
    citation: Citation = Field(
        description="Source citation with document name, page number, and quote",
    )
    nli_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Raw NLI entailment score from citation verification",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Combined three-signal confidence (NLI + retrieval + LLM)",
    )
    confidence_level: str = Field(
        default="low",
        description="Human-readable confidence level: high, medium, or low",
    )
    requires_review: bool = Field(
        default=True,
        description="Whether this requirement needs human review",
    )


class RequirementsChecklist(BaseModel):
    """Complete assembled requirements checklist for a project.

    Groups verified requirements into three lists:
    - requirements: Technical, commercial, legal, and HSE requirements.
    - submission_documents: Mandatory documents to be submitted with the tender.
    - eligibility_criteria: Pre-qualification and eligibility requirements.
    """

    requirements: list[VerifiedRequirement] = Field(
        default_factory=list,
        description="Technical, commercial, legal, and HSE requirements",
    )
    submission_documents: list[VerifiedRequirement] = Field(
        default_factory=list,
        description="Mandatory documents to be submitted with the tender",
    )
    eligibility_criteria: list[VerifiedRequirement] = Field(
        default_factory=list,
        description="Pre-qualification and eligibility requirements",
    )
    total_count: int = Field(
        default=0,
        description="Total number of requirements across all lists",
    )
    mandatory_count: int = Field(
        default=0,
        description="Number of mandatory requirements across all lists",
    )
    categories_extracted: list[str] = Field(
        default_factory=list,
        description="Which categories were successfully extracted",
    )


class ChecklistResponse(BaseModel):
    """API response wrapper for checklist extraction results."""

    project_id: int = Field(
        description="ID of the project this checklist belongs to",
    )
    status: str = Field(
        description='Extraction status: "completed", "in_progress", "failed", or "not_started"',
    )
    checklist: RequirementsChecklist | None = Field(
        default=None,
        description="The extracted requirements checklist, if available",
    )
    extraction_time_seconds: float | None = Field(
        default=None,
        description="Time taken for checklist extraction in seconds",
    )
    total_requirements: int = Field(
        default=0,
        description="Total number of requirements extracted",
    )
    requirements_requiring_review: int = Field(
        default=0,
        description="Number of requirements flagged for human review",
    )
