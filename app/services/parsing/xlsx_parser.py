"""XLSX parser using openpyxl with multi-sheet support.

Parses Excel spreadsheets into the uniform ParsedDocument structure.
Each worksheet becomes a separate PageContent entry. Cell data is
preserved as pipe-delimited tables.

Uses openpyxl with read_only=True and data_only=True for memory
efficiency (avoids loading entire workbook into memory).
"""

import asyncio
import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface


class XlsxParser(ParserInterface):
    """Parse XLSX/XLS files using openpyxl.

    Each sheet is treated as a separate "page". Cell values are converted
    to strings and organized into tables with headers derived from the
    first row of each sheet.

    Attributes:
        supported_extensions: [".xlsx", ".xls"]
    """

    supported_extensions: list[str] = [".xlsx", ".xls"]

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse an XLSX file and return a uniform ParsedDocument.

        Placeholder -- full implementation in Task 2.
        """
        raise NotImplementedError("XlsxParser.parse() not yet implemented")
