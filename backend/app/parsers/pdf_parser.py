"""PDF document parser using PyMuPDF with OCR fallback."""

import time
from pathlib import Path
from typing import Optional

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry


@ParserRegistry.register
class PDFParser(BaseParser):
    """Parser for PDF documents.

    Uses PyMuPDF (fitz) for text extraction with pytesseract OCR fallback
    for scanned documents.
    """

    supported_extensions = [".pdf"]
    supported_mimetypes = ["application/pdf"]

    # Minimum text threshold to determine if OCR is needed
    MIN_TEXT_THRESHOLD = 100

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse a PDF document.

        Args:
            file_path: Path to PDF file

        Returns:
            ParsedContent with extracted text and metadata
        """
        import fitz  # PyMuPDF

        self.validate_file(file_path)
        start_time = time.time()

        pages = []
        full_text = []
        tables = []
        warnings = []

        try:
            doc = fitz.open(file_path)

            for page_num, page in enumerate(doc):
                # Extract text
                text = page.get_text("text")
                pages.append(text)
                full_text.append(f"[Page {page_num + 1}]\n{text}")

                # Try to extract tables
                try:
                    page_tables = page.find_tables()
                    for tab in page_tables:
                        tables.append({
                            "page": page_num + 1,
                            "data": tab.extract()
                        })
                except Exception:
                    pass  # Table extraction is optional

            combined_text = "\n\n".join(full_text)

            # Check if we need OCR (scanned document)
            if len(combined_text.strip()) < self.MIN_TEXT_THRESHOLD:
                warnings.append("Low text content detected, attempting OCR")
                try:
                    ocr_text = await self._ocr_pdf(file_path)
                    if ocr_text:
                        combined_text = ocr_text
                        pages = ocr_text.split("[Page ")
                        pages = [f"[Page {p}" for p in pages if p.strip()]
                except Exception as e:
                    warnings.append(f"OCR failed: {str(e)}")

            # Extract metadata
            metadata = await self.extract_metadata(file_path)

            processing_time = int((time.time() - start_time) * 1000)

            return ParsedContent(
                text=combined_text,
                metadata=metadata,
                pages=pages if pages else None,
                tables=tables if tables else None,
                page_count=len(doc),
                processing_time_ms=processing_time,
                warnings=warnings,
            )

        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}") from e

    async def _ocr_pdf(self, file_path: str) -> str:
        """Perform OCR on a scanned PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text from OCR
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract

            from app.config import get_settings
            settings = get_settings()

            # Convert PDF pages to images
            images = convert_from_path(file_path, dpi=300)
            text_parts = []

            for i, image in enumerate(images):
                # Perform OCR with Arabic + English
                text = pytesseract.image_to_string(
                    image,
                    lang=settings.TESSERACT_LANG,
                    config="--oem 3 --psm 3"
                )
                text_parts.append(f"[Page {i + 1}]\n{text}")

            return "\n\n".join(text_parts)

        except ImportError:
            raise ImportError(
                "OCR requires pdf2image and pytesseract. "
                "Install with: pip install pdf2image pytesseract"
            )
        except Exception as e:
            raise Exception(f"OCR failed: {str(e)}") from e

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            Dictionary of metadata
        """
        import fitz

        try:
            doc = fitz.open(file_path)
            meta = doc.metadata

            return {
                "title": meta.get("title") or None,
                "author": meta.get("author") or None,
                "subject": meta.get("subject") or None,
                "creator": meta.get("creator") or None,
                "producer": meta.get("producer") or None,
                "creation_date": meta.get("creationDate") or None,
                "modification_date": meta.get("modDate") or None,
                "page_count": len(doc),
                "file_size": Path(file_path).stat().st_size,
            }
        except Exception:
            return {
                "page_count": 0,
                "file_size": Path(file_path).stat().st_size,
            }
