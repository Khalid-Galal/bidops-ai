"""Prompt templates for LLM operations."""

from app.prompts.project_summary import (
    PROJECT_SUMMARY_PROMPT,
    PROJECT_SUMMARY_SCHEMA,
    build_summary_prompt,
)
from app.prompts.checklist import (
    CHECKLIST_PROMPT,
    CHECKLIST_SCHEMA,
    build_checklist_prompt,
)
from app.prompts.classification import (
    DOCUMENT_CLASSIFICATION_PROMPT,
    BOQ_CLASSIFICATION_PROMPT,
)

__all__ = [
    "PROJECT_SUMMARY_PROMPT",
    "PROJECT_SUMMARY_SCHEMA",
    "build_summary_prompt",
    "CHECKLIST_PROMPT",
    "CHECKLIST_SCHEMA",
    "build_checklist_prompt",
    "DOCUMENT_CLASSIFICATION_PROMPT",
    "BOQ_CLASSIFICATION_PROMPT",
]
