async def test_email_parser_reads_eml(tmp_path):
    from email.message import EmailMessage
    from app.services.parsing.email_parser import EmailParser

    msg = EmailMessage()
    msg["Subject"] = "RFQ - Concrete Package"
    msg["From"] = "buyer@acme.test"
    msg["To"] = "sales@supplier.test"
    msg.set_content("Please quote the attached BOQ. Deadline 20 April.")

    f = tmp_path / "mail.eml"
    f.write_bytes(bytes(msg))

    parsed = await EmailParser().parse(str(f))
    assert parsed.content_type == "eml"
    assert "RFQ - Concrete Package" in parsed.full_text
    assert "buyer@acme.test" in parsed.full_text
    assert "Please quote" in parsed.full_text
    assert parsed.metadata.get("subject") == "RFQ - Concrete Package"


def test_email_parser_extensions():
    from app.services.parsing.email_parser import EmailParser
    p = EmailParser()
    assert p.can_parse("x.eml") and p.can_parse("y.msg")
