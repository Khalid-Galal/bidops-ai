import pytest


async def test_text_parser_reads_plain_text(tmp_path):
    from app.services.parsing.text_parser import TextParser

    f = tmp_path / "note.txt"
    f.write_text("Tender deadline: 20 April 2026.\nBond: 5,000,000.", encoding="utf-8")

    parsed = await TextParser().parse(str(f))
    assert parsed.content_type == "txt"
    assert "Tender deadline" in parsed.full_text
    assert parsed.page_count == 1
    assert parsed.pages[0].page_number == 1
    assert "Bond" in parsed.pages[0].text


def test_text_parser_supports_extensions():
    from app.services.parsing.text_parser import TextParser

    p = TextParser()
    assert p.can_parse("a.txt") and p.can_parse("b.md") and p.can_parse("c.csv")
    assert not p.can_parse("d.pdf")
