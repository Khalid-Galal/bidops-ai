import zipfile


async def test_zip_parser_aggregates_supported_members(tmp_path):
    from app.services.parsing.zip_parser import ZipParser

    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "Alpha tender note")
        zf.writestr("b.md", "# Beta spec section")
        zf.writestr("ignore.xyz", "unsupported binary")

    parsed = await ZipParser().parse(str(z))
    assert parsed.content_type == "zip"
    assert "Alpha tender note" in parsed.full_text
    assert "Beta spec section" in parsed.full_text
    # two supported members -> two pages; unsupported member noted in warnings
    assert parsed.page_count == 2
    assert any("ignore.xyz" in w for w in parsed.warnings)
