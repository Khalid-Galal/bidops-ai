"""Document parsers module."""

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry
from app.parsers.pdf_parser import PDFParser
from app.parsers.docx_parser import DocxParser
from app.parsers.xlsx_parser import XlsxParser
from app.parsers.pptx_parser import PptxParser
from app.parsers.text_parser import TextParser
from app.parsers.email_parser import EmailParser
from app.parsers.image_parser import ImageParser

__all__ = [
    "BaseParser",
    "ParsedContent",
    "ParserRegistry",
    "PDFParser",
    "DocxParser",
    "XlsxParser",
    "PptxParser",
    "TextParser",
    "EmailParser",
    "ImageParser",
]
