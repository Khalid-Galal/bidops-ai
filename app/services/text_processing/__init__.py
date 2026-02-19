"""Bilingual text processing services for Arabic/English content.

Provides Arabic text normalization, language detection, and post-OCR text
cleanup for mixed Arabic/English tender documents. These services are consumed
by the chunking, indexing, and search pipelines.

Usage:
    from app.services.text_processing import (
        normalize_arabic,
        normalize_for_search,
        detect_language,
        detect_languages_per_section,
        clean_ocr_text,
    )
"""

from app.services.text_processing.arabic_normalizer import (
    normalize_arabic,
    normalize_for_search,
)
from app.services.text_processing.language_detector import (
    detect_language,
    detect_languages_per_section,
)
from app.services.text_processing.text_cleaner import clean_ocr_text

__all__ = [
    "normalize_arabic",
    "normalize_for_search",
    "detect_language",
    "detect_languages_per_section",
    "clean_ocr_text",
]
