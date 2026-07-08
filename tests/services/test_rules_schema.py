import json
import pathlib


def test_rules_config_validates_default_json():
    from app.schemas.rules import RulesConfig

    data = json.loads(
        pathlib.Path("config/rules.default.json").read_text(encoding="utf-8")
    )
    cfg = RulesConfig.model_validate(data)
    assert cfg.commercial.currency == "USD"
    assert cfg.commercial.vat_rate == 0.0
    assert cfg.email.default_language == "en"
    assert cfg.measurement.unit_mappings["sqm"] == "m2"
    assert cfg.packaging.trade_categories["electrical"]
    assert cfg.packaging.trade_categories["mechanical"]
    assert cfg.packaging.trade_categories["plumbing"]
    assert cfg.packaging.trade_categories["fire_fighting"]
    assert "mep" not in cfg.packaging.trade_categories
    assert cfg.indirects.location_factors["default"] == 1.0
    # weights round-trip
    assert abs(sum(cfg.scoring.weights.model_dump().values()) - 1.0) < 1e-9


def test_rules_config_defaults_construct_without_file():
    from app.schemas.rules import RulesConfig

    cfg = RulesConfig()  # all sections have defaults
    assert cfg.commercial.currency == "USD"
    assert cfg.email.default_language == "en"


def test_rules_config_rejects_unknown_keys():
    import pytest
    from pydantic import ValidationError

    from app.schemas.rules import RulesConfig

    with pytest.raises(ValidationError):
        RulesConfig.model_validate({"commercial": {"vat_rat": 0.1}})
