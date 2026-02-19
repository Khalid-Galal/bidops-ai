"""Category definitions with search queries and prompts for requirements checklist extraction.

Each CategoryDefinition drives per-category retrieval and extraction:
- `queries` provides multiple search terms for hybrid search per category.
- `top_k_per_query` controls chunks retrieved per individual query.
- `max_context_chunks` caps total unique chunks after deduplication across queries.
- `prompt_hints` provides category-specific LLM extraction guidance.

Six categories cover all requirement types in construction tenders:
Technical, Commercial, Legal, HSE, Submission Documents, Eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RequirementCategory = Literal[
    "technical",
    "commercial",
    "legal",
    "hse",
    "submission_documents",
    "eligibility",
]


@dataclass
class CategoryDefinition:
    """Definition of a requirement category for extraction.

    Each category specifies multiple search queries to maximize recall,
    retrieval parameters for chunk count, and prompt hints that guide
    the LLM to extract only requirements relevant to this category.
    """

    name: RequirementCategory
    display_name: str
    description: str
    queries: list[str] = field(default_factory=list)
    top_k_per_query: int = 8
    max_context_chunks: int = 20
    prompt_hints: str = ""


CHECKLIST_CATEGORIES: list[CategoryDefinition] = [
    CategoryDefinition(
        name="technical",
        display_name="Technical",
        description="Technical specifications, standards, materials, testing, workmanship, design criteria",
        queries=[
            "technical requirements specifications standards",
            "material requirements testing inspection quality workmanship",
            "design requirements drawings calculations tolerances",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: technical specifications, referenced standards (BS, ASTM, ISO, EN), "
            "material requirements, testing and inspection, workmanship, tolerances, "
            "design criteria, methodology, and equipment requirements."
        ),
    ),
    CategoryDefinition(
        name="commercial",
        display_name="Commercial",
        description="Pricing, payment, bonds, insurance, warranties, financial requirements",
        queries=[
            "commercial requirements pricing payment terms",
            "insurance requirements warranty bond guarantee",
            "financial requirements tender bond advance payment retention",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: pricing format, payment conditions, bonds and guarantees, "
            "insurance requirements, warranty periods, retention, advance payment, "
            "cost breakdowns, and financial obligations."
        ),
    ),
    CategoryDefinition(
        name="legal",
        display_name="Legal",
        description="Contract conditions, dispute resolution, applicable law, compliance, intellectual property",
        queries=[
            "legal requirements conditions of contract applicable law",
            "dispute resolution arbitration governing law compliance",
            "intellectual property confidentiality indemnity liability",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: contractual obligations, conditions of contract, applicable law, "
            "dispute resolution, compliance requirements, indemnity, liability limitations, "
            "intellectual property, confidentiality, and regulatory compliance."
        ),
    ),
    CategoryDefinition(
        name="hse",
        display_name="HSE",
        description="Health, safety, environment requirements, plans, permits",
        queries=[
            "health safety environment requirements HSE plan",
            "safety requirements PPE training risk assessment",
            "environmental requirements waste management permits",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: HSE plans, safety certifications, PPE requirements, "
            "risk assessments, environmental management, waste disposal, "
            "permits and licenses, safety training, incident reporting, "
            "and environmental impact measures."
        ),
    ),
    CategoryDefinition(
        name="submission_documents",
        display_name="Submission Documents",
        description="Mandatory documents to be submitted with the tender",
        queries=[
            "documents to be submitted tender submission requirements",
            "required documents certificates appendices schedules",
            "submission checklist tender form deliverables",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: all documents that must be submitted with the tender, "
            "including forms, certificates, declarations, schedules, appendices, "
            "pricing documents, technical proposals, and any attachments. "
            "Note whether each document is mandatory or optional."
        ),
    ),
    CategoryDefinition(
        name="eligibility",
        display_name="Eligibility / Pre-Qualification",
        description="Pre-qualification criteria, eligibility requirements, minimum qualifications",
        queries=[
            "eligibility criteria pre-qualification requirements minimum",
            "experience requirements financial capacity turnover",
            "required certifications licenses registrations",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: minimum experience requirements, financial standing criteria, "
            "required certifications and licenses, technical capacity requirements, "
            "similar project experience, key personnel qualifications, "
            "and any disqualification criteria. These are CRITICAL for bid/no-bid decisions."
        ),
    ),
]
