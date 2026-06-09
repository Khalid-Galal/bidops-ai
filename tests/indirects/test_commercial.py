from app.schemas.rules import RulesConfig
from app.services.pricing.commercial import compute_commercial


def test_compute_commercial_default_markups():
    rules = RulesConfig()  # default markup: overhead .08, profit .10, contingency .05, risk .03; vat 0.0
    out = compute_commercial(1000.0, rules)
    assert out["markups"] == {
        "overhead": 80.0, "profit": 100.0, "contingency": 50.0, "risk": 30.0,
        "markup_total": 260.0,
    }
    assert out["selling_before_vat"] == 1260.0
    assert out["vat_rate"] == 0.0
    assert out["vat_amount"] == 0.0
    assert out["grand_total"] == 1260.0


def test_compute_commercial_applies_vat():
    rules = RulesConfig()
    rules.commercial.vat_rate = 0.10
    out = compute_commercial(1000.0, rules)
    assert out["selling_before_vat"] == 1260.0
    assert out["vat_amount"] == 126.0
    assert out["grand_total"] == 1386.0


def test_compute_commercial_zero_base():
    out = compute_commercial(0.0, RulesConfig())
    assert out["markups"]["markup_total"] == 0.0
    assert out["grand_total"] == 0.0
