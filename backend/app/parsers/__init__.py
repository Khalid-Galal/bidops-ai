"""Document parsers module.

Import base classes directly. Parser implementations are loaded lazily.
"""

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry

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


def __getattr__(name: str):
    """Lazy import parsers."""
    if name == "PDFParser":
        from app.parsers.pdf_parser import PDFParser
        return PDFParser
    elif name == "DocxParser":
        from app.parsers.docx_parser import DocxParser
        return DocxParser
    elif name == "XlsxParser":
        from app.parsers.xlsx_parser import XlsxParser
        return XlsxParser
    elif name == "PptxParser":
        from app.parsers.pptx_parser import PptxParser
        return PptxParser
    elif name == "TextParser":
        from app.parsers.text_parser import TextParser
        return TextParser
    elif name == "EmailParser":
        from app.parsers.email_parser import EmailParser
        return EmailParser
    elif name == "ImageParser":
        from app.parsers.image_parser import ImageParser
        return ImageParser
    raise AttributeError(f"module 'app.parsers' has no attribute '{name}'")
