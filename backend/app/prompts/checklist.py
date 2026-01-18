"""Prompt templates for requirements checklist generation."""

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "category": {"type": "string"},
                    "requirement": {"type": "string"},
                    "description": {"type": "string"},
                    "mandatory": {"type": "boolean"},
                    "source_document": {"type": ["string", "null"]},
                    "source_reference": {"type": ["string", "null"]},
                    "responsible_party": {"type": ["string", "null"]},
                    "deadline": {"type": ["string", "null"]},
                    "deliverable": {"type": ["string", "null"]},
                }
            }
        }
    }
}

CHECKLIST_PROMPT = """You are an expert tender compliance analyst. Your task is to extract all requirements from tender documents that a contractor must comply with.

## Instructions

1. Analyze the provided tender documents carefully
2. Identify ALL requirements, obligations, and conditions
3. Categorize each requirement appropriately
4. Mark mandatory requirements (using words like "shall", "must", "required")
5. Include document references for traceability

## Categories to Use

- **SUBMISSION**: Document submission requirements
- **QUALIFICATION**: Pre-qualification and eligibility requirements
- **TECHNICAL**: Technical specifications and standards
- **COMMERCIAL**: Pricing, payment, and financial requirements
- **LEGAL**: Legal, insurance, and contractual requirements
- **HSE**: Health, Safety, and Environment requirements
- **QUALITY**: Quality assurance and control requirements
- **SCHEDULE**: Timeline and milestone requirements
- **BONDS**: Bond and guarantee requirements
- **DOCUMENTATION**: Required documents and certifications

## Document Context

{context}

## Response Format

Respond with a JSON object containing a "requirements" array:

```json
{{
  "requirements": [
    {{
      "id": 1,
      "category": "SUBMISSION",
      "requirement": "Submit tender in sealed envelope",
      "description": "Tender must be submitted in a sealed envelope marked with project name and tender reference",
      "mandatory": true,
      "source_document": "ITT_Document.pdf",
      "source_reference": "Section 3.1, Page 5",
      "responsible_party": "Tenderer",
      "deadline": "2024-03-15 14:00",
      "deliverable": "Sealed tender envelope"
    }},
    {{
      "id": 2,
      "category": "QUALIFICATION",
      "requirement": "Minimum 5 years experience",
      "description": "Contractor must demonstrate minimum 5 years experience in similar projects",
      "mandatory": true,
      "source_document": "Pre-Qualification.pdf",
      "source_reference": "Section 2.1",
      "responsible_party": "Tenderer",
      "deadline": null,
      "deliverable": "Experience certificates"
    }}
  ]
}}
```

## Important Notes

- Extract EVERY requirement, even if seemingly minor
- "Shall", "must", "required" indicate mandatory requirements
- "Should", "may", "recommended" indicate non-mandatory items
- Include specific quantities, percentages, and deadlines where mentioned
- Look for requirements in:
  - Instructions to Tenderers (ITT)
  - Conditions of Contract
  - Technical Specifications
  - Particular Conditions
  - Appendices and Schedules

Be thorough. Missing a requirement could lead to disqualification."""


def build_checklist_prompt(documents: list[dict]) -> str:
    """Build the checklist generation prompt with document context.

    Args:
        documents: List of document excerpts with metadata
            [{"filename": "...", "content": "...", "category": "..."}]

    Returns:
        Complete prompt string
    """
    context_parts = []

    # Sort by relevance (ITT and contract docs first)
    priority_keywords = ["itt", "instruction", "condition", "requirement", "qualification"]

    def get_priority(doc):
        filename = doc.get("filename", "").lower()
        category = doc.get("category", "").lower()
        for i, kw in enumerate(priority_keywords):
            if kw in filename or kw in category:
                return i
        return len(priority_keywords)

    sorted_docs = sorted(documents, key=get_priority)

    for doc in sorted_docs:
        filename = doc.get("filename", "Unknown")
        category = doc.get("category", "")
        content = doc.get("content", "")

        # Truncate very long content
        if len(content) > 10000:
            content = content[:10000] + "\n\n[... content truncated ...]"

        context_parts.append(f"""
### Document: {filename}
Category: {category}

{content}
""")

    context = "\n---\n".join(context_parts)

    return CHECKLIST_PROMPT.format(context=context)


CHECKLIST_CATEGORIES = [
    "SUBMISSION",
    "QUALIFICATION",
    "TECHNICAL",
    "COMMERCIAL",
    "LEGAL",
    "HSE",
    "QUALITY",
    "SCHEDULE",
    "BONDS",
    "DOCUMENTATION",
]
