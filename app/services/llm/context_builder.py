"""Labeled context assembly from SearchResult chunks for LLM attribution.

Formats retrieved document chunks with [SOURCE:filename | PAGE:N] labels
so the LLM can produce accurate citations referencing specific documents
and page numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.extraction.checklist_definitions import CategoryDefinition
    from app.services.extraction.field_definitions import FieldDefinition
    from app.services.search.hybrid_search import SearchResult


def build_labeled_context(chunks: list[SearchResult]) -> str:
    """Build context string with labeled source chunks for LLM attribution.

    Each chunk is prefixed with source metadata that the LLM
    can reference in citation output.

    Args:
        chunks: List of SearchResult objects from hybrid search.

    Returns:
        Concatenated context string with source labels and separators.
    """
    parts: list[str] = []
    for chunk in chunks:
        label = f"[SOURCE:{chunk.filename} | PAGE:{chunk.page_number}]"
        parts.append(f"{label}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)


def build_extraction_prompt(field_def: FieldDefinition, context: str) -> str:
    """Build extraction prompt for a specific field with source context.

    Creates a detailed prompt instructing the LLM to extract one field
    from the provided document excerpts, with extractive citation
    requirements.

    Args:
        field_def: The field definition with name, description, and type.
        context: Labeled context string from build_labeled_context().

    Returns:
        Complete prompt string ready for LLM extraction.
    """
    enum_line = ""
    if field_def.enum_values:
        enum_line = f"VALID VALUES: {', '.join(field_def.enum_values)}\n"

    extra_instructions = ""
    if field_def.field_type == "list":
        extra_instructions = (
            "\n9. Return the value as a comma-separated list of items."
        )
    elif field_def.field_type == "date":
        extra_instructions = (
            "\n9. Preserve the date format exactly as it appears in the source"
            " (do not convert or reformat)."
        )

    prompt = f"""\
Extract the following field from the tender document excerpts below.

FIELD: {field_def.name}
DESCRIPTION: {field_def.description}
EXPECTED TYPE: {field_def.field_type}
{enum_line}
INSTRUCTIONS:
1. Find the {field_def.name} in the provided document excerpts.
2. Copy the EXACT value as it appears in the source document.
3. For the quote field in citations, copy the EXACT sentence(s) containing this value -- do NOT paraphrase or summarize.
4. Include the document_name and page_number from the [SOURCE:... | PAGE:...] labels in your citation.
5. If the field is not found in any excerpt, set value to null and confidence to 0.0.
6. NEVER fabricate or infer values not explicitly stated in the documents.
7. For list-type fields (e.g., stakeholders), include ALL items found across all excerpts.
8. Set confidence between 0.0 and 1.0 based on how clearly and explicitly the value appears.{extra_instructions}

DOCUMENT EXCERPTS:
{context}"""

    return prompt


def build_checklist_extraction_prompt(
    category: CategoryDefinition,
    context: str,
) -> str:
    """Build extraction prompt for one requirement category with source context.

    Creates a category-focused prompt instructing the LLM to extract all
    requirements of a specific type from the provided document excerpts,
    with mandatory classification guidance and citation requirements.

    Args:
        category: The category definition with name, description, and hints.
        context: Labeled context string from build_labeled_context().

    Returns:
        Complete prompt string ready for LLM extraction.
    """
    # Build list of other categories to explicitly skip
    all_categories = [
        "Technical", "Commercial", "Legal", "HSE",
        "Submission Documents", "Eligibility / Pre-Qualification",
    ]
    other_categories = [c for c in all_categories if c != category.display_name]
    skip_list = ", ".join(other_categories)

    prompt = f"""\
Extract ALL {category.display_name} requirements from the tender document excerpts below.

CATEGORY: {category.display_name}
CATEGORY DESCRIPTION: {category.description}

{category.prompt_hints}

INSTRUCTIONS:
1. Extract EVERY {category.display_name.lower()} requirement, obligation, or condition found in the excerpts.
2. For mandatory classification: "shall", "must", "required", "mandatory" = is_mandatory: true. "should", "may", "recommended", "desirable" = is_mandatory: false. For ambiguous language, default to mandatory (safer for tender compliance).
3. ONLY extract {category.display_name.lower()} requirements. Skip requirements that belong to other categories ({skip_list}).
4. Do NOT fabricate or infer requirements not explicitly stated in the documents.
5. If no {category.display_name.lower()} requirements are found, return an empty items list.
6. Be thorough -- missing a requirement could lead to tender disqualification.

DOCUMENT EXCERPTS:
{context}"""

    return prompt
