"""Document parsing pipeline -- multi-format parser registry.

Provides a uniform interface for parsing PDF, DOCX, and XLSX files into
a common ParsedDocument structure. Use ``get_parser_for_file()`` to obtain
the correct parser for any supported filename.

Example::

    from app.services.parsing import get_parser_for_file

    parser = get_parser_for_file("tender_spec.pdf")
    result = await parser.parse("/path/to/tender_spec.pdf")
    print(result.full_text[:200])
"""

from app.services.parsing.base import (
    PageContent,
    ParsedDocument,
    ParserInterface,
    get_parser_for_file,
)
from app.services.parsing.pdf_parser import PdfParser
from app.services.parsing.docx_parser import DocxParser
from app.services.parsing.xlsx_parser import XlsxParser

__all__ = [
    "PageContent",
    "ParsedDocument",
    "ParserInterface",
    "get_parser_for_file",
    "PdfParser",
    "DocxParser",
    "XlsxParser",
]
