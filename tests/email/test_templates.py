import pytest

from app.services.email.templates import html_to_text, render_body

CTX = {
    "contact_name": "Sara",
    "project_name": "Metro",
    "package_name": "HVAC Package",
    "package_code": "PKG-001-HVAC",
    "trade_category": "Mep",
    "scope_description": "Supply & install <b>chillers</b>",
    "deadline": "2026-07-01",
    "submission_instructions": "Email your offer.",
    "attachments": [{"name": "Brief.pdf"}, {"name": "BOQ.xlsx"}],
    "sender_name": "BidOps AI",
    "company_name": "BidOps",
    "custom_message": "Note the site visit.",
}


def test_render_en_contains_key_fields_and_escapes():
    html = render_body("rfq", "en", CTX)
    assert "Sara" in html
    assert "HVAC Package" in html
    assert "Brief.pdf" in html and "BOQ.xlsx" in html
    assert "Note the site visit." in html
    # autoescape: the literal scope HTML must be escaped, not injected as a tag
    assert "<b>chillers</b>" not in html
    assert "&lt;b&gt;chillers&lt;/b&gt;" in html


def test_render_ar_is_rtl():
    html = render_body("rfq", "ar", CTX)
    assert 'dir="rtl"' in html
    assert "Sara" in html  # interpolated values still present


def test_unknown_language_falls_back_to_en():
    assert render_body("rfq", "fr", CTX) == render_body("rfq", "en", CTX)


def test_reminder_template_renders():
    html = render_body("reminder", "en", {**CTX, "time_remaining": "3 days"})
    assert "HVAC Package" in html


def test_html_to_text_strips_tags():
    txt = html_to_text("<p>Hello&nbsp;<b>World</b></p>")
    assert "Hello" in txt and "World" in txt
    assert "<" not in txt and ">" not in txt
