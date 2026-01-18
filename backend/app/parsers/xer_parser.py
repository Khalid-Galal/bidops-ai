"""Primavera XER file parser."""

import time
from pathlib import Path
from typing import Dict, List

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry


@ParserRegistry.register
class XERParser(BaseParser):
    """Parser for Primavera P6 XER export files."""

    supported_extensions = [".xer"]
    supported_mimetypes = ["application/octet-stream"]

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse a Primavera XER file.

        Args:
            file_path: Path to XER file

        Returns:
            ParsedContent with schedule data
        """
        self.validate_file(file_path)
        start_time = time.time()

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            tables = self._parse_xer_tables(content)

            extracted_text = []
            metadata = {
                "projects": [],
                "activities": [],
                "wbs": [],
                "resources": [],
                "file_size": Path(file_path).stat().st_size,
            }

            # Extract project info
            if "PROJECT" in tables:
                for proj in tables["PROJECT"]["data"]:
                    proj_dict = dict(zip(tables["PROJECT"]["columns"], proj))
                    project_info = {
                        "id": proj_dict.get("proj_id"),
                        "name": proj_dict.get("proj_short_name"),
                        "start": proj_dict.get("plan_start_date"),
                        "finish": proj_dict.get("plan_end_date"),
                    }
                    metadata["projects"].append(project_info)
                    extracted_text.append(
                        f"Project: {proj_dict.get('proj_short_name')} "
                        f"({proj_dict.get('plan_start_date')} - {proj_dict.get('plan_end_date')})"
                    )

            # Extract activities (TASK table)
            if "TASK" in tables:
                for task in tables["TASK"]["data"]:
                    task_dict = dict(zip(tables["TASK"]["columns"], task))
                    activity_info = {
                        "id": task_dict.get("task_id"),
                        "code": task_dict.get("task_code"),
                        "name": task_dict.get("task_name"),
                        "start": task_dict.get("act_start_date") or task_dict.get("early_start_date"),
                        "finish": task_dict.get("act_end_date") or task_dict.get("early_end_date"),
                        "duration": task_dict.get("target_drtn_hr_cnt"),
                        "status": task_dict.get("status_code"),
                    }
                    metadata["activities"].append(activity_info)
                    extracted_text.append(
                        f"Activity: {task_dict.get('task_code')} - {task_dict.get('task_name')}"
                    )

            # Extract WBS
            if "PROJWBS" in tables:
                for wbs in tables["PROJWBS"]["data"]:
                    wbs_dict = dict(zip(tables["PROJWBS"]["columns"], wbs))
                    wbs_info = {
                        "id": wbs_dict.get("wbs_id"),
                        "code": wbs_dict.get("wbs_short_name"),
                        "name": wbs_dict.get("wbs_name"),
                    }
                    metadata["wbs"].append(wbs_info)
                    extracted_text.append(
                        f"WBS: {wbs_dict.get('wbs_short_name')} - {wbs_dict.get('wbs_name')}"
                    )

            # Extract Resources
            if "RSRC" in tables:
                for rsrc in tables["RSRC"]["data"]:
                    rsrc_dict = dict(zip(tables["RSRC"]["columns"], rsrc))
                    resource_info = {
                        "id": rsrc_dict.get("rsrc_id"),
                        "name": rsrc_dict.get("rsrc_name"),
                        "type": rsrc_dict.get("rsrc_type"),
                    }
                    metadata["resources"].append(resource_info)

            full_text = "\n".join(extracted_text)

            # Add summary statistics
            metadata["activity_count"] = len(metadata["activities"])
            metadata["wbs_count"] = len(metadata["wbs"])
            metadata["resource_count"] = len(metadata["resources"])

            processing_time = int((time.time() - start_time) * 1000)

            return ParsedContent(
                text=full_text,
                metadata=metadata,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            raise Exception(f"Failed to parse XER file: {str(e)}") from e

    def _parse_xer_tables(self, content: str) -> Dict[str, dict]:
        """Parse XER file into table structures.

        Args:
            content: XER file content

        Returns:
            Dictionary of table name to columns and data
        """
        tables = {}
        current_table = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("%T"):
                # Table definition
                current_table = line[3:].strip()
                tables[current_table] = {"columns": [], "data": []}

            elif line.startswith("%F") and current_table:
                # Field definitions
                columns = line[3:].strip().split("\t")
                tables[current_table]["columns"] = columns

            elif line.startswith("%R") and current_table:
                # Data row
                values = line[3:].strip().split("\t")
                tables[current_table]["data"].append(values)

        return tables

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from XER file.

        Args:
            file_path: Path to XER file

        Returns:
            Dictionary of metadata
        """
        result = await self.parse(file_path)
        return result.metadata
