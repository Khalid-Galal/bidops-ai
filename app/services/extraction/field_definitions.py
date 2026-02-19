"""Field definitions with query hints for all 13 project summary extraction fields.

Each FieldDefinition drives per-field retrieval from hybrid search:
- `query` is the primary search query sent to HybridSearchService.
- `query_hints` are additional search terms for display and future use.
- `top_k` controls how many chunks to retrieve per field.
- `field_type` guides LLM extraction and validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FieldDefinition:
    """Definition of an extraction field with retrieval hints."""

    name: str
    description: str
    field_type: Literal["text", "date", "number", "currency", "list", "enum"]
    query: str
    query_hints: list[str] = field(default_factory=list)
    top_k: int = 5
    required: bool = True
    enum_values: list[str] | None = None


SUMMARY_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="project_name",
        description="Official name or title of the construction project",
        field_type="text",
        query="project name title tender",
        query_hints=["project name", "tender for", "project title"],
        top_k=5,
    ),
    FieldDefinition(
        name="project_owner",
        description="Client or entity issuing the tender (employer/owner)",
        field_type="text",
        query="project owner client employer authority",
        query_hints=["owner", "client", "employer", "authority", "issued by"],
        top_k=5,
    ),
    FieldDefinition(
        name="location",
        description="Geographic location or site address of the project",
        field_type="text",
        query="project location site address area city",
        query_hints=["location", "site", "address", "located at", "project site"],
        top_k=3,
    ),
    FieldDefinition(
        name="submission_deadline",
        description="Final date and time for tender submission",
        field_type="date",
        query="submission deadline closing date due date",
        query_hints=["deadline", "submission date", "due date", "closing date", "last date"],
        top_k=5,
    ),
    FieldDefinition(
        name="bid_validity_period",
        description="Period for which the bid must remain valid",
        field_type="text",
        query="bid validity period tender validity",
        query_hints=["validity", "valid for", "bid validity"],
        top_k=3,
    ),
    FieldDefinition(
        name="pre_bid_meeting_date",
        description="Date and details of pre-bid meeting or site visit",
        field_type="date",
        query="pre-bid meeting site visit mandatory site inspection",
        query_hints=["pre-bid", "site visit", "meeting", "inspection"],
        top_k=3,
    ),
    FieldDefinition(
        name="scope_of_work",
        description="Summary of the works included in the tender",
        field_type="text",
        query="scope of work description of works project scope",
        query_hints=["scope", "works", "description of works", "scope of work"],
        top_k=8,
    ),
    FieldDefinition(
        name="contract_type",
        description="Type of contract (lump sum, remeasured, unit rate, etc.)",
        field_type="enum",
        query="contract type lump sum remeasured unit rate",
        query_hints=["lump sum", "remeasured", "unit rate", "contract type", "type of contract"],
        enum_values=["lump_sum", "remeasured", "unit_rate", "cost_plus", "design_build", "other"],
        top_k=3,
    ),
    FieldDefinition(
        name="tender_bond",
        description="Required tender bond or bid security amount and form",
        field_type="currency",
        query="tender bond bid security bid bond guarantee",
        query_hints=["tender bond", "bid security", "bid bond", "bank guarantee"],
        top_k=3,
    ),
    FieldDefinition(
        name="advance_payment",
        description="Advance payment percentage or amount",
        field_type="text",
        query="advance payment mobilization advance",
        query_hints=["advance payment", "mobilization", "advance"],
        top_k=3,
    ),
    FieldDefinition(
        name="retention_percentage",
        description="Retention percentage held from payments",
        field_type="text",
        query="retention percentage withheld payment",
        query_hints=["retention", "withheld", "retention percentage"],
        top_k=3,
    ),
    FieldDefinition(
        name="payment_terms",
        description="Payment cycle, terms, and conditions",
        field_type="text",
        query="payment terms cycle interim payment monthly",
        query_hints=["payment terms", "interim payment", "monthly payment", "payment cycle"],
        top_k=5,
    ),
    FieldDefinition(
        name="stakeholders",
        description="List of stakeholders: consultants, PMC, designer, engineer",
        field_type="list",
        query="consultant PMC project management designer engineer",
        query_hints=["consultant", "PMC", "project management", "designer", "engineer", "supervisor"],
        top_k=5,
    ),
]
