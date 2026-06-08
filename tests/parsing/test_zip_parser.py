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


async def test_nested_zip_depth_guard(tmp_path):
    from app.services.parsing.zip_parser import ZipParser

    # build inner.zip (contains a.txt) nested several levels deep
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("a.txt", "deep content")
    cur = inner.read_bytes()
    for i in range(5):  # nest 5 levels -> exceeds default max_depth=3
        nxt = tmp_path / f"n{i}.zip"
        with zipfile.ZipFile(nxt, "w") as zf:
            zf.writestr("inner.zip", cur)
        cur = nxt.read_bytes()
    outer = tmp_path / "outer.zip"
    outer.write_bytes(cur)
    parsed = await ZipParser(max_depth=3).parse(str(outer))
    # must terminate and warn, not recurse infinitely
    assert any("max depth" in w.lower() for w in parsed.warnings)
