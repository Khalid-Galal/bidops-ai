"""Plain text file parser."""

import time
from pathlib import Path
import chardet

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry


@ParserRegistry.register
class TextParser(BaseParser):
    """Parser for plain text files."""

    supported_extensions = [".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".log"]
    supported_mimetypes = [
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/xml",
        "text/xml",
        "application/x-yaml",
    ]

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse a text file.

        Args:
            file_path: Path to text file

        Returns:
            ParsedContent with file contents
        """
        self.validate_file(file_path)
        start_time = time.time()

        try:
            # Detect encoding
            with open(file_path, "rb") as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected.get("encoding", "utf-8")

            # Read file with detected encoding
            try:
                text = raw_data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # Fallback to utf-8 with error handling
                text = raw_data.decode("utf-8", errors="replace")

            # Extract metadata
            metadata = await self.extract_metadata(file_path)
            metadata["encoding"] = encoding
            metadata["line_count"] = text.count("\n") + 1

            processing_time = int((time.time() - start_time) * 1000)

            return ParsedContent(
                text=text,
                metadata=metadata,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            raise Exception(f"Failed to parse text file: {str(e)}") from e

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from text file.

        Args:
            file_path: Path to text file

        Returns:
            Dictionary of metadata
        """
        path = Path(file_path)
        stat = path.stat()

        return {
            "file_size": stat.st_size,
            "file_extension": path.suffix,
            "modified_time": stat.st_mtime,
        }
