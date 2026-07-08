"""Labeled context assembly from SearchResult chunks for LLM attribution.

Formats retrieved document chunks with [SOURCE:filename | PAGE:N] labels
so the LLM can produce accurate citations referencing specific documents
and page numbers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.extraction.checklist_definitions import CategoryDefinition
    from app.services.extraction.field_definitions import FieldDefinition
    from app.services.search.hybrid_search import SearchResult

# Matches the filename inside a "[SOURCE:<filename> | PAGE:<n>]" label so the
# valid document names can be enumerated back to the LLM.
_SOURCE_LABEL = re.compile(r"\[SOURCE:(.*?) \| PAGE:")


def _valid_documents_block(context: str) -> str:
    """Enumerate the unique source filenames present in a labeled context.

    Listing the exact filenames the LLM may cite lets it copy the value
    character-for-character instead of paraphrasing or re-casing it, which is
    what the downstream citation matcher expects.
    """
    seen: list[str] = []
    for name in _SOURCE_LABEL.findall(context):
        name = name.strip()
        if name and name not in seen:
            seen.append(name)
    if not seen:
        return ""
    listing = "\n".join(f"- {name}" for name in seen)
    return (
        "\nVALID DOCUMENTS (copy the filename EXACTLY as one of these into"
        f" your citation, character-for-character):\n{listing}\n"
    )


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

    valid_documents = _valid_documents_block(context)

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
2. {"Copy the EXACT value as it appears in the source document." if not field_def.enum_values else "Map the value found in the document to the closest matching token from VALID VALUES above and return that exact snake_case token (not the document's wording)."}
3. For the quote field in citations, copy the EXACT sentence(s) containing this value from the source document -- do NOT paraphrase or summarize, and do NOT substitute the VALID VALUES token here.
4. For document_name, copy the filename EXACTLY as it appears between SOURCE: and | in the labels -- do NOT translate, re-case, or drop the extension -- and include the page_number from the same label.
5. If the field is not found in any excerpt, set value to null and confidence to 0.0.
6. NEVER fabricate or infer values not explicitly stated in the documents.
7. For list-type fields (e.g., stakeholders), include ALL items found across all excerpts.
8. Set confidence between 0.0 and 1.0 based on how clearly and explicitly the value appears.{extra_instructions}
{valid_documents}
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
    valid_documents = _valid_documents_block(context)

    prompt = f"""\
Extract ALL {category.display_name} requirements from the tender document excerpts below.

CATEGORY: {category.display_name}
CATEGORY DESCRIPTION: {category.description}

{category.prompt_hints}

INSTRUCTIONS:
1. Extract EVERY {category.display_name.lower()} requirement, obligation, or condition found in the excerpts.
2. For mandatory classification: "shall", "must", "required", "mandatory" = is_mandatory: true. "should", "may", "recommended", "desirable" = is_mandatory: false. For ambiguous language, default to mandatory (safer for tender compliance).
3. Category precedence: any DOCUMENT that must be SUBMITTED with the bid belongs to Submission Documents, even when its content is commercial, legal, or eligibility-related. Under that rule, extract an item here only if it is a {category.display_name.lower()} requirement, and leave requirements owned by another category to that category.
4. Do NOT fabricate or infer requirements not explicitly stated in the documents.
5. If no {category.display_name.lower()} requirements are found, return an empty items list.
6. Be thorough -- missing a requirement could lead to tender disqualification.
7. For source_document, copy the filename EXACTLY as it appears between SOURCE: and | in the labels -- do NOT translate, re-case, or drop the extension. For quote, copy the exact sentence(s) verbatim -- do NOT paraphrase.
{valid_documents}
DOCUMENT EXCERPTS:
{context}"""

    return prompt
