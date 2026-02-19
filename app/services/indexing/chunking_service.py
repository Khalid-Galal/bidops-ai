"""Semantic document chunking with Arabic-aware separators.

Splits parsed documents into ~400-character chunks that respect semantic
boundaries (paragraphs, sentences, Arabic comma breaks). Tables are always
emitted as single chunks -- never split mid-row.

Each chunk carries source metadata (document_id, page_number, language,
section name, character offsets) so that search results can provide
precise citations back to the original document location.

Chunking strategy:
1. For each page, emit table chunks first (one chunk per table).
2. Split remaining page text using recursive character splitting.
3. Apply overlap between consecutive text chunks for continuity.
4. Detect language and normalize text for each chunk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.parsing.base import PageContent
from app.services.text_processing import detect_language, normalize_for_search

logger = logging.getLogger(__name__)

# Separators ordered by preference: try paragraph breaks first, then
# sentence endings (English and Arabic), then clause-level breaks.
_SEPARATORS = ["\n\n", "\n", ". ", ".\u060C ", "\u060C ", ", ", " "]


@dataclass
class DocumentChunk:
    """A single chunk of a parsed document, ready for embedding.

    Attributes:
        chunk_id: Unique identifier with format
            "{document_id}_p{page_number}_c{chunk_index}" for text chunks or
            "{document_id}_p{page_number}_t{table_index}" for table chunks.
        document_id: Foreign key to the Document table.
        page_number: 1-based source page number (for citations).
        text: Original chunk text (for display to users).
        text_normalized: Normalized text (for embedding and BM25 indexing).
        language: Detected language -- "ar", "en", "mixed", or "unknown".
        chunk_type: Either "text" or "table".
        section_name: Detected section heading if any, else None.
        char_start: Character offset start in the page text.
        char_end: Character offset end in the page text.
        metadata: Additional metadata (filename, etc.).
    """

    chunk_id: str
    document_id: int
    page_number: int
    text: str
    text_normalized: str
    language: str
    chunk_type: str
    section_name: str | None
    char_start: int
    char_end: int
    metadata: dict = field(default_factory=dict)


class ChunkingService:
    """Splits parsed documents into semantically meaningful chunks.

    Uses recursive character splitting with Arabic-aware separators to
    produce chunks of approximately ``max_chunk_chars`` characters. Tables
    are always kept as single chunks regardless of size.

    Args:
        max_chunk_chars: Target maximum characters per chunk (default 400).
        overlap_chars: Number of characters to overlap between consecutive
            text chunks for context continuity (default 50).
    """

    def __init__(
        self,
        max_chunk_chars: int = 400,
        overlap_chars: int = 50,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    def chunk_document(
        self,
        document_id: int,
        pages: list[PageContent],
        filename: str,
    ) -> list[DocumentChunk]:
        """Chunk a parsed document into embeddable segments.

        For each page: first emit table chunks (one per table, never
        split), then split remaining page text at semantic boundaries.

        Args:
            document_id: Database ID of the source document.
            pages: List of PageContent objects from the parser.
            filename: Original filename for metadata.

        Returns:
            List of DocumentChunk objects with all metadata populated.
        """
        all_chunks: list[DocumentChunk] = []

        for page in pages:
            page_num = page.page_number

            # --- Table chunks: one chunk per table, never split ---
            for t_idx, table in enumerate(page.tables):
                table_text = self._table_to_text(table)
                if not table_text.strip():
                    continue

                chunk_id = f"{document_id}_p{page_num}_t{t_idx}"
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page_num,
                        text=table_text,
                        text_normalized=normalize_for_search(table_text),
                        language=detect_language(table_text),
                        chunk_type="table",
                        section_name=None,
                        char_start=0,
                        char_end=0,
                        metadata={"filename": filename},
                    )
                )

            # --- Text chunks: recursive semantic splitting ---
            page_text = page.text
            if not page_text or not page_text.strip():
                continue

            text_spans = self._split_text(page_text)

            # Apply overlap between consecutive spans.
            overlapped_spans = self._apply_overlap(page_text, text_spans)

            for c_idx, (span_text, start, end) in enumerate(overlapped_spans):
                if not span_text.strip():
                    continue

                chunk_id = f"{document_id}_p{page_num}_c{c_idx}"
                section_name = self._detect_section_heading(span_text)

                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page_num,
                        text=span_text,
                        text_normalized=normalize_for_search(span_text),
                        language=detect_language(span_text),
                        chunk_type="text",
                        section_name=section_name,
                        char_start=start,
                        char_end=end,
                        metadata={"filename": filename},
                    )
                )

        logger.info(
            "Chunked document %d (%s): %d chunks from %d pages",
            document_id,
            filename,
            len(all_chunks),
            len(pages),
        )
        return all_chunks

    def _split_text(self, text: str) -> list[tuple[str, int, int]]:
        """Recursively split text into chunks respecting semantic boundaries.

        Tries separators in order of preference (paragraph breaks first,
        then sentence endings, etc.). If a segment is still too large after
        trying all separators, it is included as-is (no forced mid-word split).

        Args:
            text: Text to split.

        Returns:
            List of (chunk_text, char_start, char_end) tuples with offsets
            relative to the input text.
        """
        if len(text) <= self.max_chunk_chars:
            return [(text, 0, len(text))]

        return self._recursive_split(text, 0, 0)

    def _recursive_split(
        self,
        text: str,
        base_offset: int,
        separator_index: int,
    ) -> list[tuple[str, int, int]]:
        """Recursive splitting implementation.

        Args:
            text: Text segment to split.
            base_offset: Character offset of this segment in the original
                page text.
            separator_index: Current index into the _SEPARATORS list
                (which separator to try).

        Returns:
            List of (chunk_text, char_start, char_end) tuples.
        """
        # Base case: text fits within max_chunk_chars.
        if len(text) <= self.max_chunk_chars:
            return [(text, base_offset, base_offset + len(text))]

        # Base case: no more separators to try -- return text as-is.
        if separator_index >= len(_SEPARATORS):
            return [(text, base_offset, base_offset + len(text))]

        sep = _SEPARATORS[separator_index]
        parts = text.split(sep)

        # If separator didn't split anything, try the next one.
        if len(parts) <= 1:
            return self._recursive_split(text, base_offset, separator_index + 1)

        # Merge parts into chunks that fit within max_chunk_chars.
        result: list[tuple[str, int, int]] = []
        current_parts: list[str] = []
        current_len = 0
        current_start = base_offset

        for part in parts:
            # Calculate the length this part would add (including separator).
            add_len = len(part) + (len(sep) if current_parts else 0)

            if current_len + add_len > self.max_chunk_chars and current_parts:
                # Flush current accumulation as a chunk.
                merged = sep.join(current_parts)
                chunk_end = current_start + len(merged)

                if len(merged) > self.max_chunk_chars:
                    # Still too large -- recurse with next separator.
                    sub_chunks = self._recursive_split(
                        merged, current_start, separator_index + 1
                    )
                    result.extend(sub_chunks)
                else:
                    result.append((merged, current_start, chunk_end))

                # Start new accumulation after the separator.
                current_start = chunk_end + len(sep)
                current_parts = [part]
                current_len = len(part)
            else:
                current_parts.append(part)
                current_len += add_len

        # Flush remaining parts.
        if current_parts:
            merged = sep.join(current_parts)
            chunk_end = current_start + len(merged)

            if len(merged) > self.max_chunk_chars:
                sub_chunks = self._recursive_split(
                    merged, current_start, separator_index + 1
                )
                result.extend(sub_chunks)
            else:
                result.append((merged, current_start, chunk_end))

        return result

    def _apply_overlap(
        self,
        full_text: str,
        spans: list[tuple[str, int, int]],
    ) -> list[tuple[str, int, int]]:
        """Add overlap between consecutive text spans.

        For each span after the first, prepend up to ``overlap_chars``
        characters from the end of the previous span's source text.

        Args:
            full_text: The full page text (for extracting overlap content).
            spans: List of (text, start, end) tuples from _split_text.

        Returns:
            New list of spans with overlap applied. The start offset of
            overlapping spans is adjusted to reflect the earlier start.
        """
        if len(spans) <= 1 or self.overlap_chars <= 0:
            return spans

        result = [spans[0]]

        for i in range(1, len(spans)):
            _text, start, end = spans[i]

            # Calculate overlap start: go back overlap_chars from current start,
            # but don't go before the beginning of the text.
            overlap_start = max(0, start - self.overlap_chars)
            overlapped_text = full_text[overlap_start:end]

            result.append((overlapped_text, overlap_start, end))

        return result

    @staticmethod
    def _table_to_text(table: dict) -> str:
        """Convert a table dict to pipe-separated text for embedding.

        Format:
            | header1 | header2 |
            | val1 | val2 |
            | val3 | val4 |

        Args:
            table: Dict with "headers" (list[str]) and "data" (list[list[str]]).

        Returns:
            Pipe-separated text representation of the table.
        """
        headers = table.get("headers", [])
        data = table.get("data", [])

        lines = []

        if headers:
            header_line = "| " + " | ".join(str(h) for h in headers) + " |"
            lines.append(header_line)

        for row in data:
            row_line = "| " + " | ".join(str(cell) for cell in row) + " |"
            lines.append(row_line)

        return "\n".join(lines)

    @staticmethod
    def _detect_section_heading(text: str) -> str | None:
        """Detect if a chunk starts with a section heading.

        Heuristic: if the chunk starts with a short line (< 80 chars)
        followed by a newline, treat that first line as a section heading.

        Args:
            text: Chunk text to inspect.

        Returns:
            The detected section heading string, or None.
        """
        if "\n" not in text:
            return None

        first_line, _ = text.split("\n", 1)
        first_line = first_line.strip()

        if first_line and len(first_line) < 80:
            return first_line

        return None
