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
    assert cfg.email.draft_only is True
    assert cfg.measurement.unit_mappings["sqm"] == "m2"
    assert cfg.packaging.trade_categories["mep"]
    assert cfg.indirects.location_factors["default"] == 1.0
    # weights round-trip
    assert abs(sum(cfg.scoring.weights.model_dump().values()) - 1.0) < 1e-9


def test_rules_config_defaults_construct_without_file():
    from app.schemas.rules import RulesConfig

    cfg = RulesConfig()  # all sections have defaults
    assert cfg.commercial.currency == "USD"
    assert cfg.email.provider == "smtp"
