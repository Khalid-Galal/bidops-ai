"""Per-section language detection for Arabic/English content.

Uses lingua-language-detector (Rust-compiled) for fast, accurate language
detection on both short and long text segments. Supports detection of
mixed-language content with per-section language boundaries.

The detector is lazily initialized at module level because building the
n-gram model takes ~100ms. Once built, detection calls are fast (<1ms).

Language codes returned:
- "ar": Arabic
- "en": English
- "mixed": Both Arabic and English detected in the same text
- "unknown": Text too short or language could not be determined
"""

import re

from lingua import Language, LanguageDetectorBuilder

# Lazy-initialized detector -- built on first use.
# Only loads Arabic and English models to reduce false positives and
# improve accuracy on construction tender terminology.
_detector = None

# Minimum text length (stripped) for reliable detection.
_MIN_TEXT_LENGTH = 10

# Regex patterns for quick script detection.
_ARABIC_CHAR_PATTERN = re.compile(r"[\u0600-\u06FF]")
_LATIN_CHAR_PATTERN = re.compile(r"[a-zA-Z]")


def _get_detector():
    """Get or create the language detector instance.

    The detector is built once and cached at module level. Building
    takes ~100ms but subsequent calls are <1ms.

    Returns:
        A configured lingua LanguageDetector instance.
    """
    global _detector
    if _detector is not None:
        return _detector

    _detector = (
        LanguageDetectorBuilder.from_languages(Language.ARABIC, Language.ENGLISH)
        .build()
    )
    return _detector


def _has_both_scripts(text: str) -> bool:
    """Check if text contains both Arabic and Latin script characters.

    This quick check avoids expensive per-section detection when text
    is purely one script.
    """
    return bool(_ARABIC_CHAR_PATTERN.search(text)) and bool(
        _LATIN_CHAR_PATTERN.search(text)
    )


def detect_language(text: str) -> str:
    """Detect the primary language of a text segment.

    For short text (<10 chars stripped), returns "unknown" because
    language detection is unreliable on very short strings.

    For text containing both Arabic and Latin script characters, uses
    per-section detection to check for mixed content. If multiple
    language sections are found, returns "mixed".

    For single-script text, uses lingua's primary detection.

    Args:
        text: Text to detect the language of. May be pure Arabic,
              pure English, or mixed.

    Returns:
        One of: "ar", "en", "mixed", "unknown"

    Examples:
        >>> detect_language("Hello world, this is English text")
        'en'
        >>> detect_language("مرحبا بالعالم")
        'ar'
        >>> detect_language("Hello مرحبا mixed text content here")
        'mixed'
        >>> detect_language("hi")
        'unknown'
    """
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        return "unknown"

    detector = _get_detector()

    # Quick script check: if both Arabic and Latin characters are present,
    # use per-section detection to identify mixed content. This catches
    # cases where lingua's primary detection is confident about one
    # language but the text genuinely contains both.
    if _has_both_scripts(text):
        try:
            sections = detector.detect_multiple_languages_of(text)
            languages_found = set()
            for section in sections:
                if section.language == Language.ARABIC:
                    languages_found.add("ar")
                elif section.language == Language.ENGLISH:
                    languages_found.add("en")

            if "ar" in languages_found and "en" in languages_found:
                return "mixed"
            elif "ar" in languages_found:
                return "ar"
            elif "en" in languages_found:
                return "en"
        except Exception:
            # If multi-language detection fails, fall through to
            # primary detection below.
            pass

    # Single-script text or mixed detection failed: use primary detection.
    detected = detector.detect_language_of(text)

    if detected == Language.ARABIC:
        return "ar"
    elif detected == Language.ENGLISH:
        return "en"

    return "unknown"


def detect_languages_per_section(text: str) -> list[dict]:
    """Detect language boundaries in mixed-language text.

    Uses lingua's multi-language detection to identify contiguous sections
    of Arabic and English text. This is used by the chunking service
    (Plan 02-02) to tag chunks with language metadata and optimize
    chunking at language boundaries.

    Args:
        text: Text that may contain mixed Arabic and English content.

    Returns:
        List of dicts, each with:
        - "language": "ar" or "en"
        - "start": Character start index in the input text
        - "end": Character end index in the input text
        - "text": The text segment for this language section

        Returns an empty list if text is too short or detection fails.

    Examples:
        >>> sections = detect_languages_per_section("Hello world مرحبا بالعالم")
        >>> len(sections) >= 2
        True
        >>> sections[0]["language"] in ("ar", "en")
        True
    """
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        return []

    detector = _get_detector()

    try:
        results = detector.detect_multiple_languages_of(text)
    except Exception:
        return []

    sections = []
    for result in results:
        if result.language == Language.ARABIC:
            lang_code = "ar"
        elif result.language == Language.ENGLISH:
            lang_code = "en"
        else:
            lang_code = "unknown"

        sections.append({
            "language": lang_code,
            "start": result.start_index,
            "end": result.end_index,
            "text": text[result.start_index:result.end_index],
        })

    return sections
