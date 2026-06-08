"""ZIP archive parser: extracts members and recursively parses supported files."""

from __future__ import annotations

import tempfile
import time
import zipfile
from pathlib import Path

from app.services.parsing.base import (
    PageContent,
    ParsedDocument,
    ParserInterface,
    get_parser_for_file,
)


class ZipParser(ParserInterface):
    """Extracts a .zip and aggregates parsed text from supported members.

    Each supported member becomes one page (labelled with its archive path).
    Unsupported members and per-member parse failures are recorded as warnings,
    never raised, so a partially-parseable archive still ingests.
    """

    supported_extensions = [".zip"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        warnings: list[str] = []
        pages: list[PageContent] = []
        tables: list[dict] = []
        texts: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            try:
                with zipfile.ZipFile(file_path) as zf:
                    members = [m for m in zf.namelist() if not m.endswith("/")]
                    for member in members:
                        try:
                            parser = get_parser_for_file(member)
                        except ValueError:
                            warnings.append(f"Skipped unsupported member: {member}")
                            continue
                        extracted = Path(zf.extract(member, tmp))
                        try:
                            sub = await parser.parse(str(extracted))
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"Failed to parse member {member}: {exc}")
                            continue
                        page_no = len(pages) + 1
                        label = f"[{member}]\n{sub.full_text}"
                        pages.append(PageContent(page_number=page_no, text=label))
                        texts.append(label)
                        for t in sub.tables:
                            tables.append({**t, "source_member": member})
                        warnings.extend(f"{member}: {w}" for w in sub.warnings)
            except zipfile.BadZipFile:
                warnings.append("Invalid or corrupt ZIP archive.")

        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=Path(file_path).name,
            content_type="zip",
            full_text="\n\n".join(texts),
            pages=pages,
            tables=tables,
            metadata={"member_count": len(pages)},
            page_count=len(pages),
            processing_time_ms=elapsed,
            warnings=warnings,
        )
