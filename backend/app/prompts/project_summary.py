"""Prompt templates for project summary extraction."""

PROJECT_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {
            "type": "object",
            "properties": {
                "value": {"type": ["string", "null"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "document": {"type": "string"},
                            "page": {"type": ["string", "integer", "null"]},
                            "snippet": {"type": "string"}
                        }
                    }
                }
            }
        },
        "project_owner": {"$ref": "#/properties/project_name"},
        "main_contractor": {"$ref": "#/properties/project_name"},
        "location": {"$ref": "#/properties/project_name"},
        "submission_deadline": {"$ref": "#/properties/project_name"},
        "site_visit_date": {"$ref": "#/properties/project_name"},
        "clarification_deadline": {"$ref": "#/properties/project_name"},
        "scope_of_work": {"$ref": "#/properties/project_name"},
        "tender_bond": {"$ref": "#/properties/project_name"},
        "contract_type": {"$ref": "#/properties/project_name"},
        "contract_form": {"$ref": "#/properties/project_name"},
        "contract_duration": {"$ref": "#/properties/project_name"},
        "liquidated_damages": {"$ref": "#/properties/project_name"},
        "advance_payment": {"$ref": "#/properties/project_name"},
        "retention": {"$ref": "#/properties/project_name"},
        "performance_bond": {"$ref": "#/properties/project_name"},
        "warranty_period": {"$ref": "#/properties/project_name"},
        "payment_terms": {"$ref": "#/properties/project_name"},
        "sustainability": {"$ref": "#/properties/project_name"},
        "consultants": {"$ref": "#/properties/project_name"},
    }
}

PROJECT_SUMMARY_PROMPT = """You are an expert construction tender analyst. Your task is to extract key project information from tender documents.

## Instructions

1. Carefully analyze the provided document excerpts
2. Extract each requested field with its exact value as found in the documents
3. Provide a confidence score (0.0 to 1.0) for each extraction
4. Include evidence citations showing where you found each piece of information
5. If information is not found, set value to null and confidence to 0

## Fields to Extract

### Project Identification
- **project_name**: Official project name/title
- **project_owner**: The entity issuing the tender (client/employer)
- **main_contractor**: If specified, the contractor bidding
- **location**: Project location/site address

### Key Dates
- **submission_deadline**: Tender submission deadline (date and time)
- **site_visit_date**: Mandatory or optional site visit date
- **clarification_deadline**: Last date for clarification queries

### Scope
- **scope_of_work**: Brief description of works included

### Commercial Terms
- **tender_bond**: Required tender bond amount and form
- **contract_type**: Lump Sum, Remeasured, or Hybrid
- **contract_form**: Form of contract (FIDIC, NEC, JCT, etc.)
- **contract_duration**: Expected project duration
- **liquidated_damages**: LD amount per day/week
- **advance_payment**: Advance payment percentage
- **retention**: Retention percentage
- **performance_bond**: Performance bond percentage
- **warranty_period**: Defects liability/warranty period
- **payment_terms**: Payment cycle and terms

### Other
- **sustainability**: LEED/sustainability/green building requirements
- **consultants**: List of consultants, PMC, designers

## Document Context

{context}

## Response Format

Respond with a JSON object. For each field, provide:
- "value": The extracted value (string, number, or null if not found)
- "confidence": Confidence score from 0.0 to 1.0
- "evidence": Array of citations with document, page, and relevant snippet

Example:
```json
{{
  "project_name": {{
    "value": "Marina Tower Development Phase 2",
    "confidence": 0.95,
    "evidence": [
      {{
        "document": "ITT_Document.pdf",
        "page": "1",
        "snippet": "Invitation to Tender for Marina Tower Development Phase 2"
      }}
    ]
  }}
}}
```

Be precise. Never fabricate information. Lower confidence for ambiguous findings."""


def build_summary_prompt(documents: list[dict]) -> str:
    """Build the summary extraction prompt with document context.

    Args:
        documents: List of document excerpts with metadata
            [{"filename": "...", "content": "...", "pages": [...]}]

    Returns:
        Complete prompt string
    """
    context_parts = []

    for doc in documents:
        filename = doc.get("filename", "Unknown")
        content = doc.get("content", "")

        # Truncate very long content
        if len(content) > 15000:
            content = content[:15000] + "\n\n[... content truncated ...]"

        context_parts.append(f"""
### Document: {filename}

{content}
""")

    context = "\n---\n".join(context_parts)

    return PROJECT_SUMMARY_PROMPT.format(context=context)


SUMMARY_FIELDS = [
    "project_name",
    "project_owner",
    "main_contractor",
    "location",
    "submission_deadline",
    "site_visit_date",
    "clarification_deadline",
    "scope_of_work",
    "tender_bond",
    "contract_type",
    "contract_form",
    "contract_duration",
    "liquidated_damages",
    "advance_payment",
    "retention",
    "performance_bond",
    "warranty_period",
    "payment_terms",
    "sustainability",
    "consultants",
]
