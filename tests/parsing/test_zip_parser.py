import zipfile

import app.services.parsing.zip_parser as zip_parser_module


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


async def test_oversized_member_is_skipped(tmp_path, monkeypatch):
    from app.services.parsing.zip_parser import ZipParser

    monkeypatch.setattr(zip_parser_module, "MAX_MEMBER_SIZE_BYTES", 10)
    monkeypatch.setattr(zip_parser_module, "MAX_TOTAL_SIZE_BYTES", 10_000)

    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("small.txt", "ok")
        zf.writestr("big.txt", "x" * 1000)  # exceeds the 10-byte member cap

    parsed = await ZipParser().parse(str(z))
    assert "ok" in parsed.full_text
    assert "x" * 1000 not in parsed.full_text
    assert any("oversized" in w.lower() and "big.txt" in w for w in parsed.warnings)
    assert parsed.page_count == 1


async def test_total_size_budget_stops_extraction(tmp_path, monkeypatch):
    from app.services.parsing.zip_parser import ZipParser

    monkeypatch.setattr(zip_parser_module, "MAX_MEMBER_SIZE_BYTES", 10_000)
    monkeypatch.setattr(zip_parser_module, "MAX_TOTAL_SIZE_BYTES", 15)

    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x" * 10)
        zf.writestr("b.txt", "y" * 10)
        zf.writestr("c.txt", "z" * 10)

    parsed = await ZipParser().parse(str(z))
    # budget (15 bytes) allows only the first member before stopping
    assert parsed.page_count == 1
    assert any("budget" in w.lower() for w in parsed.warnings)
