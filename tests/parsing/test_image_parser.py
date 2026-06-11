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
    # Must NOT raise regardless of OCR availability; full_text is always a str.
    assert isinstance(parsed.full_text, str)
    if not parsed.full_text.strip():
        # Empty text is fine in BOTH environments: when no OCR engine is
        # usable an "OCR unavailable" warning must be recorded; when easyocr
        # works (python-bidi >=0.6) a blank image simply has no text and no
        # warning is expected.
        try:
            import easyocr  # noqa: F401

            ocr_available = True
        except Exception:
            ocr_available = False
        if not ocr_available:
            assert any("ocr" in w.lower() for w in parsed.warnings)


def test_image_parser_extensions():
    from app.services.parsing.image_parser import ImageParser
    p = ImageParser()
    for ext in ("a.png", "b.jpg", "c.jpeg", "d.tiff", "e.bmp"):
        assert p.can_parse(ext)
