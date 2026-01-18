"""Prompt templates for document and BOQ classification."""

DOCUMENT_CLASSIFICATION_PROMPT = """Classify the following document into one of these categories based on its content:

Categories:
- ITT: Invitation to Tender, Instructions to Bidders, RFP
- SPECS: Technical Specifications, Requirements
- BOQ: Bill of Quantities, Schedule of Rates, Pricing Schedules
- DRAWINGS: Architectural/Engineering Drawings, Plans
- CONTRACT: Contract Documents, Agreements, Terms
- ADDENDUM: Addenda, Amendments, Revisions
- CORRESPONDENCE: Letters, Emails, Communications
- SCHEDULE: Project Schedule, Programme, Timeline
- HSE: Health, Safety, Environment documents
- GENERAL: Other documents

Document filename: {filename}

Document content (first 2000 characters):
{content}

Respond with JSON:
{{
  "category": "CATEGORY_NAME",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}}"""


BOQ_CLASSIFICATION_PROMPT = """Classify the following Bill of Quantities item into a trade category.

Trade Categories:
- CIVIL: Earthwork, excavation, roads, utilities, site work
- CONCRETE: Concrete, formwork, rebar, reinforcement
- STRUCTURAL_STEEL: Steel structures, fabrication, erection
- MASONRY: Blockwork, brickwork, stonework
- WATERPROOFING: Waterproofing, damp proofing, insulation
- ROOFING: Roofing, cladding, skylights
- DOORS_WINDOWS: Doors, windows, glazing, hardware
- FINISHES: Flooring, painting, ceiling, wall finishes
- MEP_MECHANICAL: HVAC, plumbing, fire fighting, mechanical
- MEP_ELECTRICAL: Electrical, lighting, LV systems
- MEP_PLUMBING: Plumbing, drainage, water supply
- FIRE_PROTECTION: Fire alarm, suppression, detection
- ELEVATORS: Lifts, escalators, conveyors
- LANDSCAPING: Landscaping, irrigation, hardscape
- FURNITURE: FF&E, furniture, equipment
- SPECIALTIES: Specialty items, miscellaneous

BOQ Item:
- Line Number: {line_number}
- Description: {description}
- Unit: {unit}
- Section: {section}

Respond with JSON:
{{
  "trade_category": "CATEGORY_NAME",
  "trade_subcategory": "More specific subcategory if applicable",
  "confidence": 0.0-1.0,
  "keywords_matched": ["list", "of", "keywords"]
}}"""


OFFER_EXTRACTION_PROMPT = """Extract pricing and commercial information from this supplier quotation/offer.

## Supplier Offer Content:
{content}

## Package Information:
- Package Name: {package_name}
- Required Items: {required_items}

## Extract the following:

1. **Total Price**: The total quoted price
2. **Currency**: Currency of the quote
3. **Line Items**: Individual item prices if available
4. **Validity**: Quote validity period
5. **Payment Terms**: Requested payment terms
6. **Delivery Time**: Proposed delivery/completion time
7. **Exclusions**: Any items explicitly excluded
8. **Deviations**: Any deviations from specifications
9. **Conditions**: Special conditions or assumptions

Respond with JSON:
{{
  "total_price": {{
    "amount": number,
    "currency": "AED/USD/EUR/etc",
    "includes_vat": true/false
  }},
  "line_items": [
    {{
      "description": "item description",
      "unit": "unit",
      "quantity": number,
      "unit_rate": number,
      "total": number
    }}
  ],
  "validity_days": number,
  "payment_terms": "description of payment terms",
  "delivery_weeks": number,
  "exclusions": ["list of excluded items"],
  "deviations": [
    {{
      "item": "item description",
      "deviation": "how it differs from requirement"
    }}
  ],
  "conditions": ["list of conditions/assumptions"],
  "confidence": 0.0-1.0
}}"""


COMPLIANCE_CHECK_PROMPT = """Analyze this supplier offer for compliance with tender requirements.

## Tender Requirements:
{requirements}

## Supplier Offer:
{offer_content}

## Check each requirement and determine:
1. Is the requirement addressed in the offer?
2. Does the offer comply with the requirement?
3. Are there any deviations or exclusions?

Respond with JSON:
{{
  "overall_compliance": "COMPLIANT/PARTIAL/NON_COMPLIANT",
  "compliance_score": 0-100,
  "requirements_analysis": [
    {{
      "requirement_id": number,
      "requirement": "requirement text",
      "status": "MET/PARTIAL/NOT_MET/NOT_ADDRESSED",
      "evidence": "where in offer this is addressed",
      "notes": "any deviations or concerns"
    }}
  ],
  "critical_issues": ["list of critical compliance issues"],
  "clarifications_needed": ["list of items needing clarification"],
  "recommendation": "brief recommendation text"
}}"""


CLARIFICATION_DRAFT_PROMPT = """Draft a professional clarification email to a supplier based on the identified issues.

## Context:
- Project: {project_name}
- Package: {package_name}
- Supplier: {supplier_name}
- Our Company: {company_name}

## Issues Requiring Clarification:
{issues}

## Original Offer Summary:
{offer_summary}

## Instructions:
1. Write in a professional, courteous tone
2. Be specific about what information is needed
3. Reference specific sections/items from their offer
4. Set a reasonable deadline for response
5. Keep the email concise but complete

Respond with JSON:
{{
  "subject": "Email subject line",
  "body": "Full email body text",
  "key_questions": ["numbered list of main questions"],
  "suggested_deadline_days": number
}}"""
