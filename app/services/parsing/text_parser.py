"""Plain-text / markdown / CSV parser implementing ParserInterface."""

from __future__ import annotations

import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface


class TextParser(ParserInterface):
    """Parses UTF-8 (BOM/latin-1 fallback) plain-text files into one page."""

    supported_extensions = [".txt", ".md", ".csv"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        warnings: list[str] = []
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1", errors="replace")
            warnings.append("Decoded with latin-1 fallback (non-UTF-8 content).")

        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=path.name,
            content_type="txt",
            full_text=text,
            pages=[PageContent(page_number=1, text=text, tables=[])],
            tables=[],
            metadata={"char_count": len(text)},
            page_count=1,
            processing_time_ms=elapsed,
            warnings=warnings,
        )
