"""SMTP transport for outbound email. Injectable boundary for testability.

This module knows nothing about EmailLog/DB — it just sends a message. The
default constructor reads credentials from settings; pass explicit kwargs (or a
fake) in tests. is_configured() gates POST /send so missing creds degrade to a
clean 503 instead of a crash.
"""

from __future__ import annotations

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from pathlib import Path

from app.config import get_settings


class SendError(Exception):
    """Raised when the SMTP transport fails to send a message."""


class SMTPSender:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
        timeout: int = 30,
    ) -> None:
        s = get_settings()
        self.host = host if host is not None else s.smtp_host
        self.port = port if port is not None else s.smtp_port
        self.user = user if user is not None else s.smtp_user
        self.password = password if password is not None else s.smtp_password
        self.use_tls = use_tls if use_tls is not None else s.smtp_use_tls
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.host and self.user)

    def send(
        self,
        *,
        from_address: str,
        from_name: str,
        to: list[str],
        cc: list[str] | None,
        bcc: list[str] | None,
        reply_to: str | None,
        subject: str,
        body_text: str | None,
        body_html: str,
        attachments: list[dict] | None,
    ) -> str:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_address}>" if from_name else from_address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to
        message_id = make_msgid()
        msg["Message-ID"] = message_id

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text or "", "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)

        for att in attachments or []:
            path = Path(att["path"])
            if not path.exists():
                continue
            part = MIMEApplication(path.read_bytes(), Name=att["name"])
            part["Content-Disposition"] = f'attachment; filename="{att["name"]}"'
            msg.attach(part)

        recipients = list(to) + list(cc or []) + list(bcc or [])
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                if self.user:
                    server.login(self.user, self.password)
                server.sendmail(from_address, recipients, msg.as_string())
        except Exception as exc:  # noqa: BLE001 - normalize to SendError for callers
            raise SendError(str(exc)) from exc
        return message_id
