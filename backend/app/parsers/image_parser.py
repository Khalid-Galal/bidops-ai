"""Image file parser with OCR support."""

import time
from pathlib import Path
from typing import Optional

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry


@ParserRegistry.register
class ImageParser(BaseParser):
    """Parser for image files with OCR text extraction."""

    supported_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"]
    supported_mimetypes = [
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
        "image/gif",
    ]

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse an image file using OCR.

        Args:
            file_path: Path to image file

        Returns:
            ParsedContent with OCR text
        """
        self.validate_file(file_path)
        start_time = time.time()

        try:
            from PIL import Image
            import pytesseract

            from app.config import get_settings
            settings = get_settings()

            # Open and preprocess image
            image = Image.open(file_path)

            # Convert to RGB if necessary
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")

            # Perform OCR
            text = pytesseract.image_to_string(
                image,
                lang=settings.TESSERACT_LANG,
                config="--oem 3 --psm 3"
            )

            # Get image metadata
            metadata = await self.extract_metadata(file_path)
            metadata["width"] = image.width
            metadata["height"] = image.height
            metadata["mode"] = image.mode
            metadata["format"] = image.format

            processing_time = int((time.time() - start_time) * 1000)

            return ParsedContent(
                text=text.strip(),
                metadata=metadata,
                processing_time_ms=processing_time,
            )

        except ImportError:
            raise ImportError(
                "Image OCR requires PIL and pytesseract. "
                "Install with: pip install Pillow pytesseract"
            )
        except Exception as e:
            raise Exception(f"Failed to parse image: {str(e)}") from e

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from image file.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary of metadata
        """
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            image = Image.open(file_path)

            metadata = {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format,
                "file_size": Path(file_path).stat().st_size,
            }

            # Extract EXIF data if available
            exif_data = image._getexif()
            if exif_data:
                exif = {}
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if isinstance(value, (str, int, float)):
                        exif[tag] = value
                metadata["exif"] = exif

            return metadata

        except Exception:
            return {
                "file_size": Path(file_path).stat().st_size,
            }
