"""Arabic text normalization for consistent indexing and search.

Arabic has many character variants that represent the same underlying letter.
Users may type a search query with or without diacritics, with hamza or without,
using Eastern or Western numerals. Normalizing both indexed text and queries
through the same pipeline ensures that all variant forms match correctly.

Normalization steps (applied in order):
1. Remove tashkeel (diacritics) -- fatha, kasra, damma, sukun, etc.
2. Normalize alef variants -- hamza-above/below/madda to bare alef
3. Normalize teh marbuta -- replace with heh for matching consistency
4. Convert Eastern Arabic numerals -- U+0660-U+0669 to 0-9
5. Normalize whitespace -- collapse multiple spaces, strip edges

IMPORTANT: normalize_for_search() MUST be applied at both index time and query
time to ensure consistent matching. Using it at only one stage will cause
mismatches between indexed text and search queries.
"""

import re

# Try to use PyArabic for more reliable diacritics removal.
# Falls back to regex if PyArabic is unavailable.
try:
    from pyarabic.araby import strip_tashkeel as _pyarabic_strip_tashkeel

    _HAS_PYARABIC = True
except ImportError:
    _HAS_PYARABIC = False

# Regex pattern for Arabic diacritics (tashkeel): fathatan through sukun
_TASHKEEL_PATTERN = re.compile(r"[\u064B-\u0652]")

# Alef variants with hamza (above, below, madda) to normalize to bare alef
_ALEF_VARIANTS_PATTERN = re.compile(r"[\u0622\u0623\u0625]")

# Bare alef replacement character
_BARE_ALEF = "\u0627"

# Teh marbuta -> heh mapping
_TEH_MARBUTA = "\u0629"
_HEH = "\u0647"

# Eastern Arabic numerals (U+0660 to U+0669) mapped to Western digits (0-9)
_EASTERN_TO_WESTERN = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "0123456789",
)

# Whitespace normalization: collapse multiple spaces
_MULTI_SPACE_PATTERN = re.compile(r" {2,}")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for consistent storage and comparison.

    Applies a sequence of normalizations that reduce Arabic character variants
    to canonical forms. This ensures that text with or without diacritics,
    with different alef forms, or with Eastern numerals all normalize to the
    same representation.

    Args:
        text: Input text that may contain Arabic characters, mixed
              Arabic/English content, or pure English text.

    Returns:
        Normalized text with diacritics removed, alef variants unified,
        teh marbuta replaced, Eastern numerals converted, and whitespace
        collapsed.

    Examples:
        >>> normalize_arabic("مُحَمَّد")  # With diacritics
        'محمد'
        >>> normalize_arabic("أحمد إبراهيم")  # Alef variants
        'احمد ابراهيم'
        >>> normalize_arabic("١٢٣٤٥")  # Eastern numerals
        '12345'
    """
    if not text:
        return text

    # Step 1: Remove tashkeel (diacritics).
    # PyArabic's strip_tashkeel handles edge cases better than regex alone
    # (e.g., combining marks, stacking diacritics).
    if _HAS_PYARABIC:
        text = _pyarabic_strip_tashkeel(text)
    else:
        text = _TASHKEEL_PATTERN.sub("", text)

    # Step 2: Normalize alef variants.
    # Arabic has multiple alef forms (with hamza above, below, madda) that
    # users may use interchangeably. Standardize to bare alef.
    text = _ALEF_VARIANTS_PATTERN.sub(_BARE_ALEF, text)

    # Step 3: Normalize teh marbuta to heh.
    # These are often used interchangeably at word endings, especially in
    # informal or OCR-produced text.
    text = text.replace(_TEH_MARBUTA, _HEH)

    # Step 4: Convert Eastern Arabic numerals to Western digits.
    # Tender documents may use either numeral system; normalizing ensures
    # "١,٥٠٠,٠٠٠" matches "1,500,000".
    text = text.translate(_EASTERN_TO_WESTERN)

    # Step 5: Normalize whitespace.
    # OCR output often has irregular spacing. Collapse multiple spaces and
    # strip leading/trailing whitespace.
    text = _MULTI_SPACE_PATTERN.sub(" ", text)
    text = text.strip()

    return text


def normalize_for_search(text: str) -> str:
    """Normalize text for search indexing and querying.

    Applies normalize_arabic() followed by lowercasing. This function MUST
    be used at both index time and query time to ensure consistent matching
    between stored documents and search queries.

    The lowercasing step ensures case-insensitive matching for Latin
    characters in mixed Arabic/English text (Arabic has no case distinction).

    Args:
        text: Input text to normalize for search purposes.

    Returns:
        Normalized, lowercased text ready for indexing or query matching.

    Examples:
        >>> normalize_for_search("أحمد Ahmed")
        'احمد ahmed'
        >>> normalize_for_search("SCOPE OF WORK نطاق العمل")
        'scope of work نطاق العمل'
    """
    return normalize_arabic(text).lower()
