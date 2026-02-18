"""Base types and parser registry for the document parsing pipeline.

Provides uniform output types (ParsedDocument, PageContent) and a parser
interface that all format-specific parsers implement. The get_parser_for_file
registry routes files to the correct parser by extension.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageContent:
    """Content extracted from a single page (PDF/DOCX) or sheet (XLSX).

    Attributes:
        page_number: 1-based page or sheet index.
        text: Plain or markdown text content of the page.
        tables: List of table dicts, each with keys:
            {"headers": [...], "data": [[...]], "rows": int, "cols": int}
    """

    page_number: int
    text: str
    tables: list[dict] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Uniform output from all parsers regardless of input format.

    Every parser (PDF, DOCX, XLSX) returns this same structure so that
    downstream consumers never need to know the original file format.

    Attributes:
        filename: Original filename (e.g. "tender_spec.pdf").
        content_type: Format identifier -- "pdf", "docx", or "xlsx".
        full_text: Combined text for search/indexing (markdown format).
        pages: Per-page/sheet breakdown with text and tables.
        tables: All tables across the document with page numbers.
        metadata: Format-specific metadata (page_count, sheet_names, etc.).
        page_count: Total number of pages or sheets.
        processing_time_ms: Wall-clock parsing time in milliseconds.
        warnings: Non-fatal issues encountered during parsing.
    """

    filename: str
    content_type: str
    full_text: str
    pages: list[PageContent]
    tables: list[dict]
    metadata: dict
    page_count: int
    processing_time_ms: int
    warnings: list[str] = field(default_factory=list)


class ParserInterface:
    """Base class that all format-specific parsers implement.

    Subclasses must set ``supported_extensions`` and override ``parse()``.
    """

    supported_extensions: list[str] = []

    def can_parse(self, filename: str) -> bool:
        """Return True if this parser supports the given filename's extension."""
        ext = Path(filename).suffix.lower()
        return ext in self.supported_extensions

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a file and return a ParsedDocument.

        Args:
            file_path: Absolute path to the file on disk.

        Returns:
            ParsedDocument with all fields populated.

        Raises:
            NotImplementedError: If the subclass has not overridden this method.
        """
        raise NotImplementedError


def get_parser_for_file(filename: str) -> ParserInterface:
    """Return the appropriate parser instance for a given filename.

    Inspects the file extension and returns the first parser that supports it.

    Args:
        filename: Filename or path (only the extension is checked).

    Returns:
        A ParserInterface subclass instance capable of parsing the file.

    Raises:
        ValueError: If no parser supports the file's extension.
    """
    # Import here to avoid circular imports and allow lazy loading of heavy
    # dependencies (e.g. Docling models are ~2 GB on first download).
    from app.services.parsing.pdf_parser import PdfParser
    from app.services.parsing.docx_parser import DocxParser
    from app.services.parsing.xlsx_parser import XlsxParser

    parsers: list[ParserInterface] = [
        PdfParser(),
        DocxParser(),
        XlsxParser(),
    ]

    for parser in parsers:
        if parser.can_parse(filename):
            return parser

    supported = []
    for p in parsers:
        supported.extend(p.supported_extensions)
    raise ValueError(
        f"No parser available for '{filename}'. "
        f"Supported extensions: {', '.join(sorted(supported))}"
    )
