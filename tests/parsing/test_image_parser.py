async def test_image_parser_returns_metadata_and_degrades_gracefully(tmp_path):
    from PIL import Image
    from app.services.parsing.image_parser import ImageParser

    img = Image.new("RGB", (120, 40), color="white")
    f = tmp_path / "scan.png"
    img.save(str(f))

    parsed = await ImageParser().parse(str(f))
    assert parsed.content_type == "image"
    assert parsed.page_count == 1
    assert parsed.metadata.get("width") == 120 and parsed.metadata.get("height") == 40
    # OCR may be unavailable in this env -> must NOT raise; full_text is str,
    # and if no OCR engine, a warning is recorded.
    assert isinstance(parsed.full_text, str)
    if not parsed.full_text.strip():
        assert any("ocr" in w.lower() for w in parsed.warnings)


def test_image_parser_extensions():
    from app.services.parsing.image_parser import ImageParser
    p = ImageParser()
    for ext in ("a.png", "b.jpg", "c.jpeg", "d.tiff", "e.bmp"):
        assert p.can_parse(ext)
