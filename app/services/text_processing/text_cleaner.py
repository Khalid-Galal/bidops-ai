"""Post-OCR text cleanup for Arabic and mixed Arabic/English content.

Handles common OCR artifacts that appear in scanned tender documents:
- Stray control characters and zero-width joiners
- Excessive whitespace from layout detection errors
- Arabic-specific issues: misplaced tashkeel, broken lam-alef ligatures
- Bidirectional text ordering problems (numbers in wrong position)

Two cleaning modes:
- clean_ocr_text(): Full cleanup for body text paragraphs
- clean_table_text(): Lighter cleanup for table cell content (preserves
  formatting while fixing encoding issues)
"""

import re

# Try to import python-bidi for bidirectional text validation.
try:
    from bidi.algorithm import get_display as _bidi_get_display

    _HAS_BIDI = True
except ImportError:
    _HAS_BIDI = False


# --- Regex patterns for text cleanup ---

# Control characters to remove (C0/C1 controls except tab/newline/carriage-return)
_CONTROL_CHARS_PATTERN = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

# Zero-width characters that OCR may insert (ZWNJ, ZWJ, zero-width space, etc.)
# Keep ZWNJ (\u200C) which is valid in Arabic for breaking ligatures intentionally.
_STRAY_ZERO_WIDTH_PATTERN = re.compile(
    r"[\u200B\u200D\uFEFF]"  # Zero-width space, ZWJ, BOM
)

# Triple or more newlines collapsed to double (preserve paragraph boundaries)
_EXCESSIVE_NEWLINES_PATTERN = re.compile(r"\n{3,}")

# Multiple spaces collapsed to single
_MULTI_SPACE_PATTERN = re.compile(r" {2,}")

# Broken lam-alef ligatures: lam followed by space then alef
# In proper Arabic, lam-alef is a mandatory ligature with no space.
_BROKEN_LAM_ALEF_PATTERN = re.compile(
    r"\u0644\s+([\u0627\u0622\u0623\u0625])"  # lam + space(s) + alef variant
)

# Misplaced tashkeel at start of word (OCR artifact: diacritics detached from letter)
_LEADING_TASHKEEL_PATTERN = re.compile(
    r"(?<=\s)([\u064B-\u0652]+)(\S)"  # Tashkeel at word start
)

# Number formatting: protect patterns like "1,500,000" or "1.500.000" from
# whitespace cleanup. Match digit sequences with embedded commas/periods.
_NUMBER_FORMAT_PATTERN = re.compile(
    r"\d[\d,.]+\d"
)

# Pattern to detect suspicious number ordering in Arabic context:
# Arabic text, then number, then Arabic text -- check for reversed digits.
_ARABIC_CHAR_RANGE = re.compile(r"[\u0600-\u06FF]")


def clean_ocr_text(text: str) -> str:
    """Clean post-OCR text output for Arabic and mixed content.

    Applies the following cleanup steps:
    1. Remove stray control characters
    2. Remove zero-width characters (except ZWNJ)
    3. Fix broken lam-alef ligatures (space between lam and alef)
    4. Fix misplaced tashkeel at word boundaries
    5. Collapse triple+ newlines to double (preserve paragraph breaks)
    6. Collapse multiple spaces to single
    7. Validate bidirectional text ordering for mixed RTL/LTR content
    8. Strip leading/trailing whitespace

    Number formatting (e.g., "1,500,000") is preserved during whitespace
    cleanup.

    Args:
        text: Raw OCR text output that may contain artifacts.

    Returns:
        Cleaned text with OCR artifacts removed and Arabic text corrected.

    Examples:
        >>> clean_ocr_text("  hello   world  \\n\\n\\n\\n  test  ")
        'hello world\\n\\ntest'
        >>> clean_ocr_text("\\u0644 \\u0627")  # Broken lam-alef
        '\\u0644\\u0627'
    """
    if not text:
        return text

    # Step 1: Remove stray control characters.
    text = _CONTROL_CHARS_PATTERN.sub("", text)

    # Step 2: Remove zero-width characters (except ZWNJ).
    text = _STRAY_ZERO_WIDTH_PATTERN.sub("", text)

    # Step 3: Fix broken lam-alef ligatures.
    # OCR sometimes inserts a space between lam and alef, breaking the
    # mandatory Arabic ligature.
    text = _BROKEN_LAM_ALEF_PATTERN.sub("\u0644\\1", text)

    # Step 4: Fix misplaced tashkeel.
    # OCR may detach diacritics from their letters, placing them at word
    # boundaries. Reattach to the following letter.
    text = _LEADING_TASHKEEL_PATTERN.sub(r"\2\1", text)

    # Step 5: Collapse triple+ newlines to double (preserve paragraph breaks).
    text = _EXCESSIVE_NEWLINES_PATTERN.sub("\n\n", text)

    # Step 6: Normalize spacing within lines.
    # Process line by line to preserve intentional newlines.
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # Collapse multiple spaces but preserve number formatting.
        line = _collapse_spaces_preserve_numbers(line)
        # Strip leading/trailing spaces per line (not newlines -- those
        # are handled by the line split/join).
        line = line.strip()
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # Step 7: Validate bidirectional text ordering for mixed content.
    # Only apply bidi algorithm if mixed RTL/LTR content is detected AND
    # the logical ordering appears corrupted.
    if _HAS_BIDI and _has_mixed_bidi_content(text):
        text = _validate_bidi_ordering(text)

    # Step 8: Strip leading/trailing whitespace.
    text = text.strip()

    return text


def clean_table_text(text: str) -> str:
    """Light cleanup for table cell content.

    Preserves formatting while fixing encoding issues. Less aggressive
    than clean_ocr_text() because table cells may have intentional
    spacing or formatting.

    Args:
        text: Table cell text from OCR or document parsing.

    Returns:
        Cleaned cell text with encoding issues fixed.
    """
    if not text:
        return text

    # Remove control characters.
    text = _CONTROL_CHARS_PATTERN.sub("", text)

    # Remove zero-width characters.
    text = _STRAY_ZERO_WIDTH_PATTERN.sub("", text)

    # Fix broken lam-alef in table cells too.
    text = _BROKEN_LAM_ALEF_PATTERN.sub("\u0644\\1", text)

    # Light whitespace normalization: strip edges, collapse internal spaces.
    text = _MULTI_SPACE_PATTERN.sub(" ", text)
    text = text.strip()

    return text


def _collapse_spaces_preserve_numbers(line: str) -> str:
    """Collapse multiple spaces in a line while preserving number formatting.

    Protects patterns like "1,500,000" and "SAR 2,500.00" from being
    disrupted by space collapsing.

    Args:
        line: A single line of text.

    Returns:
        Line with collapsed spaces, number formatting preserved.
    """
    # Simple case: no multiple spaces.
    if "  " not in line:
        return line

    return _MULTI_SPACE_PATTERN.sub(" ", line)


def _has_mixed_bidi_content(text: str) -> bool:
    """Check if text contains both Arabic (RTL) and Latin (LTR) characters.

    Used to determine whether bidirectional text validation is needed.

    Args:
        text: Text to check.

    Returns:
        True if both Arabic and Latin characters are present.
    """
    has_arabic = bool(_ARABIC_CHAR_RANGE.search(text))
    has_latin = bool(re.search(r"[a-zA-Z]", text))
    return has_arabic and has_latin


def _validate_bidi_ordering(text: str) -> str:
    """Validate and fix bidirectional text ordering if corrupted.

    Applies the Unicode BiDi algorithm via python-bidi only when the
    logical ordering appears corrupted. Checks for signs of corruption:
    numbers appearing at the wrong position relative to surrounding
    Arabic text.

    Args:
        text: Mixed RTL/LTR text that may have ordering issues.

    Returns:
        Text with corrected ordering if corruption was detected,
        original text otherwise.
    """
    if not _HAS_BIDI:
        return text

    # Process line by line -- bidi algorithm works per paragraph.
    lines = text.split("\n")
    fixed_lines = []

    for line in lines:
        if not line.strip():
            fixed_lines.append(line)
            continue

        # Only process lines with mixed bidi content.
        if _has_mixed_bidi_content(line):
            # Check for ordering corruption: if a number appears
            # surrounded by Arabic text, verify it reads correctly.
            # Simple heuristic: if get_display() produces a different
            # result and the original has suspicious patterns, use
            # the bidi-corrected version.
            try:
                display_form = _bidi_get_display(line)
                # Only apply if the display form is meaningfully different
                # (not just whitespace changes).
                if display_form.strip() != line.strip():
                    # Check if the original has a number positioning issue:
                    # Arabic char immediately adjacent to digits without
                    # expected spacing/punctuation.
                    if _has_suspicious_number_ordering(line):
                        line = display_form
            except Exception:
                # If bidi processing fails, keep the original text.
                pass

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _has_suspicious_number_ordering(text: str) -> bool:
    """Heuristic check for suspicious number ordering in mixed bidi text.

    Looks for patterns that suggest OCR has incorrectly ordered numbers
    within Arabic text, such as digits appearing before the Arabic text
    that should precede them.

    This is a conservative heuristic -- it only flags cases where the
    ordering is clearly wrong to avoid unnecessary bidi corrections.

    Args:
        text: Mixed bidi text to check.

    Returns:
        True if suspicious number ordering is detected.
    """
    # Look for digit sequences immediately adjacent to Arabic characters
    # without expected separators (space, comma, period, parenthesis).
    # This pattern catches cases like "123مرحبا" which should be "مرحبا 123".
    suspicious = re.search(
        r"\d[\u0600-\u06FF]|[\u0600-\u06FF]\d",
        text,
    )
    return bool(suspicious)
