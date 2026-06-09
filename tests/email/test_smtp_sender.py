import smtplib

import pytest

from app.services.email.smtp_sender import SendError, SMTPSender


def test_not_configured_when_blank():
    sender = SMTPSender(host="", user="")
    assert sender.is_configured() is False


def test_configured_when_host_and_user_present():
    sender = SMTPSender(host="smtp.test", port=587, user="me@test", password="pw")
    assert sender.is_configured() is True


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.sent = None
        self.tls = False
        self.logged_in = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = (from_addr, list(to_addrs), msg)


def test_send_builds_message_and_returns_id(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    sender = SMTPSender(host="smtp.test", port=587, user="me@test", password="pw", use_tls=True)
    msg_id = sender.send(
        from_address="me@test", from_name="BidOps", to=["a@x.test"], cc=["c@x.test"],
        bcc=["b@x.test"], reply_to="reply@test", subject="Hello", body_text="hi",
        body_html="<p>hi</p>", attachments=[],
    )
    assert msg_id  # non-empty Message-ID
    fake = _FakeSMTP.instances[-1]
    assert fake.tls is True
    assert fake.logged_in == ("me@test", "pw")
    from_addr, recipients, raw = fake.sent
    assert from_addr == "me@test"
    # all of to/cc/bcc are in the envelope recipients
    assert set(recipients) == {"a@x.test", "c@x.test", "b@x.test"}
    assert "Subject: Hello" in raw


def test_send_attaches_files(monkeypatch, tmp_path):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    f = tmp_path / "doc.txt"
    f.write_text("payload")
    sender = SMTPSender(host="smtp.test", user="me@test", password="pw")
    sender.send(
        from_address="me@test", from_name="B", to=["a@x.test"], cc=None, bcc=None,
        reply_to=None, subject="S", body_text="t", body_html="<p>t</p>",
        attachments=[{"name": "doc.txt", "path": str(f)}],
    )
    raw = _FakeSMTP.instances[-1].sent[2]
    assert "doc.txt" in raw


def test_send_wraps_failure_in_senderror(monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", _boom)
    sender = SMTPSender(host="smtp.test", user="me@test", password="pw")
    with pytest.raises(SendError):
        sender.send(
            from_address="me@test", from_name="B", to=["a@x.test"], cc=None, bcc=None,
            reply_to=None, subject="S", body_text="t", body_html="<p>t</p>", attachments=[],
        )
