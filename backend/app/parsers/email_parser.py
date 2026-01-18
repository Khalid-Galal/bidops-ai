"""Email file parser for MSG and EML files."""

import time
from pathlib import Path
from email import policy
from email.parser import BytesParser
from typing import Optional

from app.parsers.base import BaseParser, ParsedContent, ParserRegistry


@ParserRegistry.register
class EmailParser(BaseParser):
    """Parser for email files (.msg, .eml)."""

    supported_extensions = [".msg", ".eml"]
    supported_mimetypes = [
        "application/vnd.ms-outlook",
        "message/rfc822",
    ]

    async def parse(self, file_path: str) -> ParsedContent:
        """Parse an email file.

        Args:
            file_path: Path to email file

        Returns:
            ParsedContent with email content
        """
        self.validate_file(file_path)
        start_time = time.time()

        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".msg":
                return await self._parse_msg(file_path, start_time)
            else:
                return await self._parse_eml(file_path, start_time)

        except Exception as e:
            raise Exception(f"Failed to parse email: {str(e)}") from e

    async def _parse_msg(self, file_path: str, start_time: float) -> ParsedContent:
        """Parse Outlook MSG file.

        Args:
            file_path: Path to MSG file
            start_time: Parse start time

        Returns:
            ParsedContent with email content
        """
        try:
            import extract_msg
        except ImportError:
            raise ImportError(
                "MSG parsing requires extract-msg. "
                "Install with: pip install extract-msg"
            )

        msg = extract_msg.Message(file_path)

        # Build email content
        parts = [
            f"From: {msg.sender}",
            f"To: {msg.to}",
            f"CC: {msg.cc}" if msg.cc else None,
            f"Subject: {msg.subject}",
            f"Date: {msg.date}",
            "",
            "--- Body ---",
            msg.body or "(No body)",
        ]

        text = "\n".join(p for p in parts if p is not None)

        # Get attachments info
        attachments = []
        for attachment in msg.attachments:
            attachments.append({
                "filename": attachment.longFilename or attachment.shortFilename,
                "size": len(attachment.data) if attachment.data else 0,
            })

        metadata = {
            "from": msg.sender,
            "to": msg.to,
            "cc": msg.cc,
            "subject": msg.subject,
            "date": str(msg.date) if msg.date else None,
            "attachments": attachments,
            "attachment_count": len(attachments),
            "file_size": Path(file_path).stat().st_size,
        }

        msg.close()

        processing_time = int((time.time() - start_time) * 1000)

        return ParsedContent(
            text=text,
            metadata=metadata,
            processing_time_ms=processing_time,
        )

    async def _parse_eml(self, file_path: str, start_time: float) -> ParsedContent:
        """Parse EML file.

        Args:
            file_path: Path to EML file
            start_time: Parse start time

        Returns:
            ParsedContent with email content
        """
        with open(file_path, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)

        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_content()
                    break
                elif content_type == "text/html" and not body:
                    # Fallback to HTML if no plain text
                    body = part.get_content()
        else:
            body = msg.get_content()

        # Build email content
        parts = [
            f"From: {msg['from']}",
            f"To: {msg['to']}",
            f"CC: {msg['cc']}" if msg["cc"] else None,
            f"Subject: {msg['subject']}",
            f"Date: {msg['date']}",
            "",
            "--- Body ---",
            body or "(No body)",
        ]

        text = "\n".join(p for p in parts if p is not None)

        # Get attachments info
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                attachments.append({
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                })

        metadata = {
            "from": msg["from"],
            "to": msg["to"],
            "cc": msg["cc"],
            "subject": msg["subject"],
            "date": msg["date"],
            "message_id": msg["message-id"],
            "attachments": attachments,
            "attachment_count": len(attachments),
            "file_size": Path(file_path).stat().st_size,
        }

        processing_time = int((time.time() - start_time) * 1000)

        return ParsedContent(
            text=text,
            metadata=metadata,
            processing_time_ms=processing_time,
        )

    async def extract_metadata(self, file_path: str) -> dict:
        """Extract metadata from email file.

        Args:
            file_path: Path to email file

        Returns:
            Dictionary of metadata
        """
        result = await self.parse(file_path)
        return result.metadata
