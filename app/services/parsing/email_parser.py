"""Email parser implementing ParserInterface.

Handles ``.eml`` via the stdlib :mod:`email` package and ``.msg`` (Outlook)
via the optional ``extract-msg`` dependency. Missing optional dependencies or
unexpected errors degrade gracefully: the parser returns a ``ParsedDocument``
with a warning and (possibly empty) text rather than raising, matching the
``document_service`` convention that parsers signal failure via warnings.
"""

from __future__ import annotations

import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

from app.services.parsing.base import PageContent, ParsedDocument, ParserInterface


class EmailParser(ParserInterface):
    """Parse ``.eml`` (stdlib) and ``.msg`` (extract-msg, graceful) files."""

    supported_extensions = [".eml", ".msg"]

    async def parse(self, file_path: str) -> ParsedDocument:
        start = time.monotonic()
        path = Path(file_path)
        ext = path.suffix.lower()
        content_type = "msg" if ext == ".msg" else "eml"

        try:
            if ext == ".msg":
                header, body, metadata, warnings = self._parse_msg(file_path)
            else:
                header, body, metadata, warnings = self._parse_eml(file_path)
        except Exception as exc:  # noqa: BLE001 -- never crash ingestion.
            elapsed = int((time.monotonic() - start) * 1000)
            return ParsedDocument(
                filename=path.name,
                content_type=content_type,
                full_text="",
                pages=[],
                tables=[],
                metadata={},
                page_count=0,
                processing_time_ms=elapsed,
                warnings=[f"Parse error: {exc}"],
            )

        full_text = f"{header}\n\n{body}".strip()
        elapsed = int((time.monotonic() - start) * 1000)
        return ParsedDocument(
            filename=path.name,
            content_type=content_type,
            full_text=full_text,
            pages=[PageContent(page_number=1, text=full_text, tables=[])],
            tables=[],
            metadata=metadata,
            page_count=1,
            processing_time_ms=elapsed,
            warnings=warnings,
        )

    @staticmethod
    def _build_header(subject, sender, to, cc, date) -> str:
        lines = [
            f"From: {sender or ''}",
            f"To: {to or ''}",
        ]
        if cc:
            lines.append(f"Cc: {cc}")
        lines.append(f"Subject: {subject or ''}")
        lines.append(f"Date: {date or ''}")
        return "\n".join(lines)

    def _parse_eml(self, file_path: str):
        warnings: list[str] = []
        with open(file_path, "rb") as fh:
            msg = BytesParser(policy=policy.default).parse(fh)

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    body = part.get_content()
                    break
                if ctype == "text/html" and not body:
                    body = part.get_content()
        else:
            body = msg.get_content()

        attachments: list[str] = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                name = part.get_filename()
                if name:
                    attachments.append(name)

        header = self._build_header(
            msg["subject"], msg["from"], msg["to"], msg["cc"], msg["date"]
        )
        metadata = {
            "subject": msg["subject"],
            "from": msg["from"],
            "to": msg["to"],
            "cc": msg["cc"],
            "date": msg["date"],
            "message_id": msg["message-id"],
            "attachments": attachments,
            "attachment_count": len(attachments),
        }
        return header, (body or ""), metadata, warnings

    def _parse_msg(self, file_path: str):
        try:
            import extract_msg
        except ImportError:
            return (
                "",
                "",
                {"attachments": [], "attachment_count": 0},
                ["extract-msg not installed; .msg body not extracted"],
            )

        warnings: list[str] = []
        msg = extract_msg.Message(file_path)
        try:
            attachments: list[str] = []
            for att in msg.attachments:
                name = att.longFilename or att.shortFilename
                if name:
                    attachments.append(name)

            header = self._build_header(
                msg.subject, msg.sender, msg.to, msg.cc, msg.date
            )
            body = msg.body or ""
            metadata = {
                "subject": msg.subject,
                "from": msg.sender,
                "to": msg.to,
                "cc": msg.cc,
                "date": str(msg.date) if msg.date else None,
                "attachments": attachments,
                "attachment_count": len(attachments),
            }
        finally:
            msg.close()

        return header, body, metadata, warnings
