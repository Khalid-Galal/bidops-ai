"""CAD file parser for DXF/DWG files."""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry
from app.config import get_settings


@ParserRegistry.register
class CADParser(BaseParser):
    """Parser for CAD files (DXF/DWG).

    DWG files are converted to DXF using ODA File Converter before parsing.
    """

    supported_extensions = [".dxf", ".dwg"]
    supported_mimetypes = [
        "application/dxf",
        "image/vnd.dxf",
        "application/acad",
        "image/vnd.dwg",
    ]

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse a CAD file.

        Args:
            file_path: Path to DXF/DWG file

        Returns:
            ParsedContent with extracted text and metadata
        """
        self.validate_file(file_path)
        start_time = time.time()

        path = Path(file_path)
        warnings = []

        try:
            # Convert DWG to DXF if necessary
            if path.suffix.lower() == ".dwg":
                dxf_path = await self._convert_dwg_to_dxf(file_path)
                if not dxf_path:
                    warnings.append("DWG conversion failed, attempting direct parse")
                    dxf_path = file_path
            else:
                dxf_path = file_path

            # Parse DXF
            return await self._parse_dxf(dxf_path, start_time, warnings)

        except Exception as e:
            raise Exception(f"Failed to parse CAD file: {str(e)}") from e

    async def _convert_dwg_to_dxf(self, dwg_path: str) -> Optional[str]:
        """Convert DWG file to DXF using ODA File Converter.

        Args:
            dwg_path: Path to DWG file

        Returns:
            Path to converted DXF file or None if conversion failed
        """
        settings = get_settings()

        if not settings.ODA_CONVERTER_PATH or not Path(settings.ODA_CONVERTER_PATH).exists():
            raise ValueError(
                "ODA File Converter not configured. "
                "Set ODA_CONVERTER_PATH in settings or download from opendesign.com"
            )

        input_dir = Path(dwg_path).parent
        output_dir = Path(tempfile.mkdtemp())

        try:
            cmd = [
                settings.ODA_CONVERTER_PATH,
                str(input_dir),
                str(output_dir),
                "ACAD2018",  # Output version
                "DXF",  # Output format
                "0",  # Recurse: 0 = no
                "1",  # Audit: 1 = yes
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                return None

            # Find converted file
            dxf_name = Path(dwg_path).stem + ".dxf"
            dxf_path = output_dir / dxf_name

            if dxf_path.exists():
                return str(dxf_path)
            return None

        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

    async def _parse_dxf(
        self, file_path: str, start_time: float, warnings: list
    ) -> ParsedContent:
        """Parse a DXF file using ezdxf.

        Args:
            file_path: Path to DXF file
            start_time: Parse start time
            warnings: List to append warnings to

        Returns:
            ParsedContent with extracted content
        """
        try:
            import ezdxf
        except ImportError:
            raise ImportError(
                "DXF parsing requires ezdxf. Install with: pip install ezdxf"
            )

        doc = ezdxf.readfile(file_path)

        extracted_text = []
        metadata = {
            "layers": [],
            "blocks": [],
            "title_block": {},
            "file_size": Path(file_path).stat().st_size,
        }

        # Extract layer names
        for layer in doc.layers:
            metadata["layers"].append(layer.dxf.name)

        # Get modelspace
        msp = doc.modelspace()

        # Extract text entities
        for entity in msp.query("TEXT MTEXT"):
            if hasattr(entity.dxf, "text"):
                extracted_text.append(entity.dxf.text)
            elif hasattr(entity, "text"):
                extracted_text.append(entity.text)

        # Extract dimension values
        for dim in msp.query("DIMENSION"):
            try:
                if hasattr(dim, "get_measurement"):
                    value = dim.get_measurement()
                    extracted_text.append(f"Dimension: {value}")
            except Exception:
                pass

        # Extract block attributes (often contain drawing info)
        for insert in msp.query("INSERT"):
            block_name = insert.dxf.name
            metadata["blocks"].append(block_name)

            try:
                for attrib in insert.attribs:
                    tag = attrib.dxf.tag
                    value = attrib.dxf.text
                    extracted_text.append(f"{tag}: {value}")

                    # Title block detection
                    tag_lower = tag.lower()
                    if any(k in tag_lower for k in ["title", "dwg", "rev", "date", "scale", "project"]):
                        metadata["title_block"][tag] = value
            except Exception:
                pass

        full_text = "\n".join(extracted_text)

        processing_time = int((time.time() - start_time) * 1000)

        return ParsedContent(
            text=full_text,
            metadata=metadata,
            processing_time_ms=processing_time,
            warnings=warnings,
        )

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from CAD file.

        Args:
            file_path: Path to CAD file

        Returns:
            Dictionary of metadata
        """
        result = await self.parse(file_path)
        return result.metadata
