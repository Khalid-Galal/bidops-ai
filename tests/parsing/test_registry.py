import pytest


@pytest.mark.parametrize(
    "filename,expected_cls",
    [
        ("a.txt", "TextParser"), ("a.md", "TextParser"), ("a.csv", "TextParser"),
        ("a.eml", "EmailParser"), ("a.msg", "EmailParser"),
        ("a.pptx", "PptxParser"),
        ("a.png", "ImageParser"), ("a.jpg", "ImageParser"),
        ("a.zip", "ZipParser"),
        ("a.pdf", "PdfParser"), ("a.docx", "DocxParser"), ("a.xlsx", "XlsxParser"),
    ],
)
def test_registry_routes_extension(filename, expected_cls):
    from app.services.parsing.base import get_parser_for_file
    assert type(get_parser_for_file(filename)).__name__ == expected_cls


def test_upload_allowlist_includes_new_formats():
    from app.api.documents import ALLOWED_EXTENSIONS
    for ext in (".txt", ".md", ".csv", ".eml", ".msg", ".pptx",
                ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".zip"):
        assert ext in ALLOWED_EXTENSIONS
