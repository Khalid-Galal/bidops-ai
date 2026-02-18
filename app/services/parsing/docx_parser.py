"""DOCX parser using Docling for structured text and table extraction.

Docling natively supports DOCX files via InputFormat.DOCX using its
SimplePipeline backend. No special pipeline options are needed for DOCX.

The converter is lazily initialized to avoid heavy imports at startup.
"""

import asyncio
import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface

# Module-level converter cache -- lazy initialization.
_converter = None


def _get_converter():
    """Create and cache a DocumentConverter configured for DOCX parsing.

    Returns:
        A configured docling.document_converter.DocumentConverter instance.
    """
    global _converter
    if _converter is not None:
        return _converter

    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat

    _converter = DocumentConverter(
        allowed_formats=[InputFormat.DOCX],
    )
    return _converter


class DocxParser(ParserInterface):
    """Parse DOCX files using Docling.

    Extracts structured text, tables, and section information from Word
    documents. Docling handles DOCX parsing with its SimplePipeline,
    producing the same iterate_items / export_to_markdown interface as PDF.

    Attributes:
        supported_extensions: [".docx"]
    """

    supported_extensions: list[str] = [".docx"]

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a DOCX file and return a uniform ParsedDocument.

        The sync Docling convert() call is wrapped in asyncio.to_thread()
        to avoid blocking the event loop.

        Args:
            file_path: Absolute path to the DOCX file.

        Returns:
            ParsedDocument with text, tables, page content, and metadata.
        """
        start_ms = time.perf_counter()
        warnings: list[str] = []

        try:
            converter = _get_converter()

            # Wrap sync Docling call in a thread.
            result = await asyncio.to_thread(converter.convert, file_path)
            doc = result.document

            # ----------------------------------------------------------
            # Extract per-page content and tables
            # ----------------------------------------------------------
            from docling_core.types.doc.labels import DocItemLabel

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
                # DOCX pages/sections are reported by Docling where available.
                # Fall back to page 1 if no provenance info.
                page_no = prov.page_no if prov else 1

                if text:
                    page_texts.setdefault(page_no, []).append(text)

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
            doc_page_count = 0
            if hasattr(doc, "pages") and doc.pages:
                doc_page_count = len(doc.pages)
            else:
                all_page_nos = list(page_texts.keys()) + list(page_tables.keys())
                doc_page_count = max(all_page_nos) if all_page_nos else 1

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
            # Full text as markdown
            # ----------------------------------------------------------
            full_text = doc.export_to_markdown()

            processing_time_ms = int((time.perf_counter() - start_ms) * 1000)

            return ParsedDocument(
                filename=Path(file_path).name,
                content_type="docx",
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
            processing_time_ms = int((time.perf_counter() - start_ms) * 1000)
            print(f"[DocxParser] Error parsing {file_path}: {exc}")
            return ParsedDocument(
                filename=Path(file_path).name,
                content_type="docx",
                full_text="",
                pages=[],
                tables=[],
                metadata={},
                page_count=0,
                processing_time_ms=processing_time_ms,
                warnings=[f"Parse error: {exc}"],
            )
