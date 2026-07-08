"""ZIP archive parser: extracts members and recursively parses supported files."""

from __future__ import annotations

import asyncio
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

# Hard cap on members processed from a single archive (zip-bomb guard).
MAX_MEMBERS = 1000

# Zip-bomb guards on decompressed size (uncompressed ZipInfo.file_size).
MAX_MEMBER_SIZE_BYTES = 200 * 1024 * 1024  # 200MB per member
MAX_TOTAL_SIZE_BYTES = 500 * 1024 * 1024  # 500MB running total per archive


class ZipParser(ParserInterface):
    """Extracts a .zip and aggregates parsed text from supported members.

    Each supported member becomes one page (labelled with its archive path).
    Unsupported members and per-member parse failures are recorded as warnings,
    never raised, so a partially-parseable archive still ingests.

    Nested archives are parsed recursively up to ``max_depth`` levels to guard
    against zip-bomb style deeply-nested archives; archives with an abusive
    number of members are truncated to the first ``MAX_MEMBERS`` entries.
    """

    supported_extensions = [".zip"]

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth

    async def parse(self, file_path: str, _depth: int = 0) -> ParsedDocument:
        start = time.monotonic()
        warnings: list[str] = []
        pages: list[PageContent] = []
        tables: list[dict] = []
        texts: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            try:
                # Reading the archive index + extracting members is blocking IO;
                # do it off the event loop.
                members = await asyncio.to_thread(_list_members, file_path)
                if len(members) > MAX_MEMBERS:
                    warnings.append(
                        f"Archive has {len(members)} members; processing only "
                        f"the first {MAX_MEMBERS}."
                    )
                    members = members[:MAX_MEMBERS]
                total_size = 0
                for member, size in members:
                    if size > MAX_MEMBER_SIZE_BYTES:
                        warnings.append(
                            f"Skipped oversized member ({size} bytes > "
                            f"{MAX_MEMBER_SIZE_BYTES} byte cap): {member}"
                        )
                        continue
                    if total_size + size > MAX_TOTAL_SIZE_BYTES:
                        warnings.append(
                            "Stopped extraction: archive's decompressed size "
                            f"budget of {MAX_TOTAL_SIZE_BYTES} bytes exceeded "
                            f"at member: {member}"
                        )
                        break
                    total_size += size
                    try:
                        parser = get_parser_for_file(member)
                    except ValueError:
                        warnings.append(f"Skipped unsupported member: {member}")
                        continue

                    # Bound recursion into nested archives.
                    if isinstance(parser, ZipParser):
                        if _depth >= self.max_depth:
                            warnings.append(
                                f"Skipped nested archive past max depth "
                                f"{self.max_depth}: {member}"
                            )
                            continue

                    extracted = await asyncio.to_thread(
                        _extract_member, file_path, member, tmp
                    )
                    try:
                        if isinstance(parser, ZipParser):
                            sub = await parser.parse(
                                str(extracted), _depth=_depth + 1
                            )
                        else:
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


def _list_members(file_path: str) -> list[tuple[str, int]]:
    """Return (name, uncompressed_size) for non-directory members (blocking)."""
    with zipfile.ZipFile(file_path) as zf:
        return [
            (info.filename, info.file_size)
            for info in zf.infolist()
            if not info.filename.endswith("/")
        ]


def _extract_member(file_path: str, member: str, dest_dir: str) -> Path:
    """Extract a single member to ``dest_dir`` and return its path (blocking)."""
    with zipfile.ZipFile(file_path) as zf:
        return Path(zf.extract(member, dest_dir))
