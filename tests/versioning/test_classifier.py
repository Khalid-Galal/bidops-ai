from app.schemas.rules import RulesConfig
from app.services.rules.rules_service import RulesService
from app.services.versioning.doc_classifier import classify_document


def _rules():
    return RulesService().load()  # real defaults from config/rules.default.json


def test_filename_classification():
    rules = _rules()
    assert classify_document("Addendum_03_Revised_Specs.pdf", "", rules)[0] == "addendum"
    assert classify_document("BOQ_Bill_of_Quantities.xlsx", "", rules)[0] == "boq"
    assert classify_document("Architectural Drawings Pkg.pdf", "", rules)[0] == "drawings"
    assert classify_document("Conditions_of_Contract.docx", "", rules)[0] == "contract"
    assert classify_document("Instructions to Tenderers.pdf", "", rules)[0] == "itt"
    assert classify_document("Mechanical_Specifications.pdf", "", rules)[0] == "specs"


def test_filename_match_has_high_confidence():
    cat, conf = classify_document("Tender BOQ final.xlsx", "", _rules())
    assert cat == "boq"
    assert conf >= 0.9


def test_text_fallback_classification():
    cat, conf = classify_document(
        "document_017.pdf",
        "This bill of quantities lists all measured works ...",
        _rules(),
    )
    assert cat == "boq"
    assert 0 < conf < 0.9


def test_no_match_returns_general():
    cat, conf = classify_document("scan_001.pdf", "lorem ipsum", _rules())
    assert cat == "general"
    assert conf == 0.0


def test_keywords_are_configurable():
    cfg = RulesConfig()
    cfg.classification.document_categories = {"hse": ["safety dossier"]}
    class _Fake:
        def load(self):
            return cfg
    cat, _ = classify_document("Project Safety Dossier.pdf", "", _Fake().load())
    assert cat == "hse"
