"""PDF parser using Docling with OCR and table structure extraction.

Uses IBM's Docling library for high-accuracy PDF parsing including:
- Native text extraction with reading order preservation
- Table structure recognition (ACCURATE mode via TableFormer)
- OCR for scanned pages (EasyOCR, English + Arabic)
- Markdown export for full-text indexing

The Docling converter is lazily initialized because:
1. It downloads ~2 GB of models on first run (Arabic OCR adds ~100 MB).
2. Import alone is heavy (PyTorch, transformers).
"""

import asyncio
import logging
import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface

logger = logging.getLogger(__name__)

# Module-level converter cache -- lazy initialization.
# NOTE: Adding Arabic to EasyOCR increases first-run model download size
# by ~100 MB (Arabic recognition model). Subsequent runs use the cached model.
_converter = None


def _get_converter():
    """Create and cache a DocumentConverter configured for PDF parsing.

    The converter is created once and reused for all subsequent parse calls.
    First invocation may take several minutes as Docling downloads model files.

    Returns:
        A configured docling.document_converter.DocumentConverter instance.
    """
    global _converter
    if _converter is not None:
        return _converter

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        EasyOcrOptions,
        TableStructureOptions,
        TableFormerMode,
    )
    from docling.datamodel.base_models import InputFormat

    pipeline_options = PdfPipelineOptions()
    # OCR is best-effort: newer docling (>=2.101) validates the OCR engine
    # EAGERLY at pipeline init, so a broken easyocr import (e.g. a python-bidi
    # version mismatch) would otherwise fail EVERY pdf -- including native-text
    # ones that need no OCR at all. Probe the import and fall back to native
    # text extraction when easyocr is unusable.
    try:
        import easyocr  # noqa: F401

        ocr_available = True
    except Exception as exc:
        logger.warning(
            "EasyOCR unavailable (%s) -- parsing PDFs without OCR "
            "(native text only; scanned pages will come back empty)",
            exc,
        )
        ocr_available = False

    pipeline_options.do_ocr = ocr_available
    if ocr_available:
        pipeline_options.ocr_options = EasyOcrOptions(
            lang=["en", "ar"],  # English + Arabic OCR (Phase 2)
            use_gpu=False,
            force_full_page_ocr=False,  # Only OCR pages with insufficient text
        )
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
        # Pass the enum member, NOT the string "ACCURATE": newer docling
        # (>=2.101) validates this field strictly and only accepts the enum /
        # its lowercase value, while older docling accepted the uppercase
        # string. The member works across both versions.
        mode=TableFormerMode.ACCURATE,  # Best accuracy for tender BOQ tables
    )

    _converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    return _converter


class PdfParser(ParserInterface):
    """Parse PDF files using Docling with OCR and table extraction.

    Handles both native (text-based) and scanned PDFs. Tables are extracted
    with structure preservation including headers, merged cells, and multi-page
    tables.

    Attributes:
        supported_extensions: [".pdf"]
    """

    supported_extensions: list[str] = [".pdf"]

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a PDF file and return a uniform ParsedDocument.

        The sync Docling convert() call is wrapped in asyncio.to_thread()
        to avoid blocking the event loop during CPU-intensive parsing.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            ParsedDocument with text, tables, page content, and metadata.
        """
        start_ms = time.perf_counter()
        warnings: list[str] = []

        try:
            converter = _get_converter()

            # Docling's convert() is synchronous and CPU-bound -- run in a
            # thread to keep the async event loop responsive.
            result = await asyncio.to_thread(converter.convert, file_path)
            doc = result.document

            # ----------------------------------------------------------
            # Extract per-page content and tables
            # ----------------------------------------------------------
            from docling_core.types.doc.labels import DocItemLabel

            # Accumulate text and tables per page number.
            page_texts: dict[int, list[str]] = {}
            page_tables: dict[int, list[dict]] = {}
            all_tables: list[dict] = []

            for item, _level in doc.iterate_items():
                label = getattr(item, "label", None)
                text = getattr(item, "text", "").strip()
                prov = (
                    item.prov[0]
                    if hasattr(item, "prov") and item.prov
                    else None
                )
                page_no = prov.page_no if prov else 1

                # Accumulate text for the page.
                if text:
                    page_texts.setdefault(page_no, []).append(text)

                # Extract tables with structure.
                if label == DocItemLabel.TABLE:
                    try:
                        df = item.export_to_dataframe(doc=doc)
                        table_dict = {
                            "page": page_no,
                            "headers": list(df.columns),
                            "data": df.values.tolist(),
                            "rows": len(df),
                            "cols": len(df.columns),
                        }
                        all_tables.append(table_dict)
                        page_tables.setdefault(page_no, []).append(table_dict)
                    except Exception as exc:
                        warnings.append(
                            f"Failed to export table on page {page_no}: {exc}"
                        )

            # ----------------------------------------------------------
            # Build PageContent objects
            # ----------------------------------------------------------
            # Determine page count from the document.
            doc_page_count = 0
            if hasattr(doc, "pages") and doc.pages:
                doc_page_count = len(doc.pages)
            else:
                # Fallback: max page number seen in items.
                all_page_nos = list(page_texts.keys()) + list(page_tables.keys())
                doc_page_count = max(all_page_nos) if all_page_nos else 0

            pages: list[PageContent] = []
            for pg in range(1, doc_page_count + 1):
                pg_text = "\n".join(page_texts.get(pg, []))
                pg_tables = page_tables.get(pg, [])
                pages.append(
                    PageContent(
                        page_number=pg,
                        text=pg_text,
                        tables=pg_tables,
                    )
                )

            # ----------------------------------------------------------
            # Full text as markdown (preserves headings, lists, tables)
            # ----------------------------------------------------------
            full_text = doc.export_to_markdown()

            processing_time_ms = int((time.perf_counter() - start_ms) * 1000)

            return ParsedDocument(
                filename=Path(file_path).name,
                content_type="pdf",
                full_text=full_text,
                pages=pages,
                tables=all_tables,
                metadata={
                    "page_count": doc_page_count,
                },
                page_count=doc_page_count,
                processing_time_ms=processing_time_ms,
                warnings=warnings,
            )

        except Exception as exc:
            # Graceful degradation: return an empty ParsedDocument with the
            # error recorded in warnings so callers never get an unhandled
            # exception from the parsing layer.
            processing_time_ms = int((time.perf_counter() - start_ms) * 1000)
            print(f"[PdfParser] Error parsing {file_path}: {exc}")
            return ParsedDocument(
                filename=Path(file_path).name,
                content_type="pdf",
                full_text="",
                pages=[],
                tables=[],
                metadata={},
                page_count=0,
                processing_time_ms=processing_time_ms,
                warnings=[f"Parse error: {exc}"],
            )
