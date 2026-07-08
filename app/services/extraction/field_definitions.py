"""Field definitions with query hints for all project summary extraction fields.

Each FieldDefinition drives per-field retrieval from hybrid search:
- `query` is the primary search query sent to HybridSearchService (English terms
  followed by their Arabic equivalents so the BM25 half of hybrid search matches
  Arabic-only tenders too).
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
        query="project name title tender اسم المشروع اسم المناقصة",
        query_hints=["project name", "tender for", "project title"],
        top_k=5,
    ),
    FieldDefinition(
        name="project_owner",
        description="Client or entity issuing the tender (employer/owner)",
        field_type="text",
        query="project owner client employer authority صاحب العمل جهة الإسناد المالك",
        query_hints=["owner", "client", "employer", "authority", "issued by"],
        top_k=5,
    ),
    FieldDefinition(
        name="location",
        description="Geographic location or site address of the project",
        field_type="text",
        query="project location site address area city موقع المشروع الموقع العنوان",
        query_hints=["location", "site", "address", "located at", "project site"],
        top_k=3,
    ),
    FieldDefinition(
        name="submission_deadline",
        description="Final date and time for tender submission",
        field_type="date",
        query="submission deadline closing date due date موعد تقديم العطاء آخر موعد للتسليم",
        query_hints=["deadline", "submission date", "due date", "closing date", "last date"],
        top_k=5,
    ),
    FieldDefinition(
        name="bid_validity_period",
        description="Period for which the bid must remain valid",
        field_type="text",
        query="bid validity period tender validity مدة سريان العطاء صلاحية العطاء",
        query_hints=["validity", "valid for", "bid validity"],
        top_k=3,
    ),
    FieldDefinition(
        name="pre_bid_meeting_date",
        description="Date and details of pre-bid meeting or site visit",
        field_type="date",
        query="pre-bid meeting site visit mandatory site inspection اجتماع ما قبل العطاء زيارة الموقع",
        query_hints=["pre-bid", "site visit", "meeting", "inspection"],
        top_k=3,
    ),
    FieldDefinition(
        name="scope_of_work",
        description="Summary of the works included in the tender",
        field_type="text",
        query="scope of work description of works project scope نطاق الأعمال وصف الأعمال",
        query_hints=["scope", "works", "description of works", "scope of work"],
        top_k=8,
    ),
    FieldDefinition(
        name="contract_type",
        description="Type of contract (lump sum, remeasured, unit rate, etc.)",
        field_type="enum",
        query="contract type lump sum remeasured unit rate نوع العقد مقطوعية إعادة قياس",
        query_hints=["lump sum", "remeasured", "unit rate", "contract type", "type of contract"],
        enum_values=["lump_sum", "remeasured", "unit_rate", "cost_plus", "design_build", "other"],
        top_k=3,
    ),
    FieldDefinition(
        name="tender_bond",
        description="Required tender bond or bid security amount and form",
        field_type="currency",
        query="tender bond bid security bid bond guarantee التأمين الابتدائي خطاب ضمان ابتدائي",
        query_hints=["tender bond", "bid security", "bid bond", "bank guarantee"],
        top_k=3,
    ),
    FieldDefinition(
        name="advance_payment",
        description="Advance payment percentage or amount",
        field_type="text",
        query="advance payment mobilization advance دفعة مقدمة دفعة التعبئة",
        query_hints=["advance payment", "mobilization", "advance"],
        top_k=3,
    ),
    FieldDefinition(
        name="retention_percentage",
        description="Retention percentage held from payments",
        field_type="text",
        query="retention percentage withheld payment محتجزات نسبة الاحتجاز",
        query_hints=["retention", "withheld", "retention percentage"],
        top_k=3,
    ),
    FieldDefinition(
        name="payment_terms",
        description="Payment cycle, terms, and conditions",
        field_type="text",
        query="payment terms cycle interim payment monthly شروط الدفع المستخلصات الدفعات",
        query_hints=["payment terms", "interim payment", "monthly payment", "payment cycle"],
        top_k=5,
    ),
    FieldDefinition(
        name="stakeholders",
        description="List of stakeholders: consultants, PMC, designer, engineer",
        field_type="list",
        query="consultant PMC project management designer engineer الاستشاري إدارة المشروع المهندس",
        query_hints=["consultant", "PMC", "project management", "designer", "engineer", "supervisor"],
        top_k=5,
    ),
    FieldDefinition(
        name="performance_bond",
        description="Required performance bond / final guarantee percentage, amount, or form",
        field_type="text",
        query="performance bond final guarantee good performance security خطاب ضمان حسن التنفيذ التأمين النهائي",
        query_hints=["performance bond", "final guarantee", "performance security", "retention bond"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="liquidated_damages",
        description="Delay penalties / liquidated damages rate and cap",
        field_type="text",
        query="liquidated damages delay penalty penalties per day cap غرامة التأخير غرامة التأخر عن التسليم",
        query_hints=["liquidated damages", "delay penalty", "penalty per day", "LD cap"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="project_duration",
        description="Contract / construction period (time for completion)",
        field_type="text",
        query="project duration contract period time for completion construction period مدة التنفيذ مدة المشروع مدة العقد",
        query_hints=["duration", "contract period", "time for completion", "completion period"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="defects_liability_period",
        description="Defects liability / maintenance / warranty period",
        field_type="text",
        query="defects liability period maintenance period warranty period فترة الصيانة فترة ضمان العيوب فترة الضمان",
        query_hints=["defects liability", "maintenance period", "warranty period", "DLP"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="insurances",
        description="Required insurances (CAR, third-party, workmen's compensation, etc.)",
        field_type="text",
        query="insurance requirements contractors all risks third party workmen compensation التأمينات بوليصة التأمين تأمين جميع الأخطار",
        query_hints=["insurance", "CAR policy", "third party", "workmen's compensation"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="clarification_deadline",
        description="Deadline for submitting queries / requests for clarification",
        field_type="date",
        query="clarification deadline queries deadline last date for questions requests for information موعد الاستفسارات آخر موعد للاستفسارات",
        query_hints=["clarification deadline", "queries deadline", "questions deadline", "RFI deadline"],
        top_k=3,
        required=False,
    ),
    FieldDefinition(
        name="main_contractor",
        description="Main contractor issuing the subcontract tender (distinct from the project owner)",
        field_type="text",
        query="main contractor general contractor prime contractor المقاول الرئيسي المقاول العام",
        query_hints=["main contractor", "general contractor", "prime contractor"],
        top_k=3,
        required=False,
    ),
]
