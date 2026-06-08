"""Image parser with graceful OCR, implementing ParserInterface.

Records image metadata (dimensions/mode/format) and attempts OCR via a
fallback chain: EasyOCR first, then pytesseract. When no OCR engine is
usable (e.g. EasyOCR currently fails to import in this environment due to a
python-bidi 0.4.2 conflict, or Tesseract is not installed), the parser
records a warning and returns empty text -- it never raises, so image
ingestion degrades gracefully rather than breaking the pipeline.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface

# Module-level EasyOCR Reader cache -- lazy, built once. Constructing a Reader
# loads detection/recognition models from disk, so we must not do it per image.
_EASYOCR_READER = None


def _get_easyocr_reader():
    """Create and cache an EasyOCR Reader for English + Arabic.

    Returns:
        A cached easyocr.Reader instance (CPU mode).
    """
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr

        _EASYOCR_READER = easyocr.Reader(["en", "ar"], gpu=False)
    return _EASYOCR_READER


class ImageParser(ParserInterface):
    """Parse image files; extract OCR text where an engine is available."""

    supported_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        path = Path(file_path)
        warnings: list[str] = []
        metadata: dict = {}

        try:
            from PIL import Image

            with Image.open(file_path) as img:
                metadata = {
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format,
                }
        except Exception as exc:  # noqa: BLE001 -- never crash ingestion.
            elapsed = int((time.monotonic() - start) * 1000)
            return ParsedDocument(
                filename=path.name,
                content_type="image",
                full_text="",
                pages=[PageContent(page_number=1, text="", tables=[])],
                tables=[],
                metadata={},
                page_count=1,
                processing_time_ms=elapsed,
                warnings=[f"Failed to open image: {exc}"],
            )

        # OCR is CPU-bound (model inference); run it off the event loop.
        text = await asyncio.to_thread(self._run_ocr, file_path, warnings)

        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=path.name,
            content_type="image",
            full_text=text,
            pages=[PageContent(page_number=1, text=text, tables=[])],
            tables=[],
            metadata=metadata,
            page_count=1,
            processing_time_ms=elapsed,
            warnings=warnings,
        )

    @staticmethod
    def _run_ocr(file_path: str, warnings: list[str]) -> str:
        """OCR with EasyOCR -> pytesseract fallback. Never raises."""
        # 1. EasyOCR (Arabic + English). Reader is built once and cached.
        try:
            reader = _get_easyocr_reader()
            result = reader.readtext(file_path, detail=0)
            return "\n".join(result).strip()
        except Exception:  # noqa: BLE001 -- fall through to next engine.
            pass

        # 2. pytesseract fallback.
        try:
            import pytesseract
            from PIL import Image

            with Image.open(file_path) as img:
                if img.mode not in ("L", "RGB"):
                    img = img.convert("RGB")
                return pytesseract.image_to_string(img, lang="eng+ara").strip()
        except Exception:  # noqa: BLE001 -- both engines unusable.
            pass

        # 3. No usable OCR engine.
        warnings.append(
            "OCR unavailable (easyocr/pytesseract not usable in this "
            "environment); image text not extracted."
        )
        return ""
