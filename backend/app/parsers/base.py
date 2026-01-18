"""Base parser interface and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Type


@dataclass
class ParsedContent:
    """Result of parsing a document."""

    # Main text content
    text: str

    # Document metadata
    metadata: dict = field(default_factory=dict)

    # Page-by-page text (for PDFs, DOCX, etc.)
    pages: Optional[list[str]] = None

    # Extracted tables as list of dicts
    tables: Optional[list[dict]] = None

    # Images extracted (as bytes)
    images: Optional[list[bytes]] = None

    # Language detected
    language: Optional[str] = None

    # Page count
    page_count: Optional[int] = None

    # Processing info
    processing_time_ms: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """Check if any content was extracted."""
        return bool(self.text and self.text.strip())

    @property
    def word_count(self) -> int:
        """Get approximate word count."""
        return len(self.text.split()) if self.text else 0


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    # File extensions this parser handles (lowercase, with dot)
    supported_extensions: list[str] = []

    # MIME types this parser handles
    supported_mimetypes: list[str] = []

    def __init__(self, config: Optional[dict] = None):
        """Initialize parser with optional configuration.

        Args:
            config: Parser-specific configuration
        """
        self.config = config or {}

    @abstractmethod
    async def parse(self, file_path: str) -> ParsedContent:
        """Parse a document and extract content.

        Args:
            file_path: Path to the document file

        Returns:
            ParsedContent with extracted text and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type not supported
            Exception: For parsing errors
        """
        pass

    @abstractmethod
    async def extract_metadata(self, file_path: str) -> dict:
        """Extract only metadata from a document.

        This is a faster operation than full parsing.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary of metadata
        """
        pass

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to check

        Returns:
            True if this parser can handle the file
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions

    def validate_file(self, file_path: str) -> None:
        """Validate that file exists and is supported.

        Args:
            file_path: Path to validate

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type not supported
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.can_parse(file_path):
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported: {self.supported_extensions}"
            )


class ParserRegistry:
    """Registry for document parsers."""

    _parsers: dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls, parser_class: Type[BaseParser]) -> Type[BaseParser]:
        """Register a parser class.

        Can be used as a decorator:
            @ParserRegistry.register
            class MyParser(BaseParser):
                ...

        Args:
            parser_class: Parser class to register

        Returns:
            The parser class (for decorator use)
        """
        for ext in parser_class.supported_extensions:
            cls._parsers[ext.lower()] = parser_class
        return parser_class

    @classmethod
    def get_parser(cls, file_path: str, config: Optional[dict] = None) -> Optional[BaseParser]:
        """Get a parser instance for the given file.

        Args:
            file_path: Path to the file
            config: Optional parser configuration

        Returns:
            Parser instance or None if no parser found
        """
        ext = Path(file_path).suffix.lower()
        parser_class = cls._parsers.get(ext)

        if parser_class:
            return parser_class(config)
        return None

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get all supported file extensions.

        Returns:
            List of supported extensions
        """
        return list(cls._parsers.keys())

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if a file type is supported.

        Args:
            file_path: Path to check

        Returns:
            True if supported
        """
        ext = Path(file_path).suffix.lower()
        return ext in cls._parsers
