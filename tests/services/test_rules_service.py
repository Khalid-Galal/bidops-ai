import json


def test_load_returns_defaults(tmp_path):
    from app.services.rules.rules_service import RulesService

    user = tmp_path / "rules.json"
    svc = RulesService(user_path=user)  # defaults_path defaults to config/rules.default.json
    cfg = svc.load()
    assert cfg.commercial.currency == "USD"
    assert cfg.email.draft_only is True


def test_save_then_load_roundtrip_with_partial_override(tmp_path):
    from app.services.rules.rules_service import RulesService
    from app.schemas.rules import RulesConfig

    user = tmp_path / "rules.json"
    svc = RulesService(user_path=user)

    cfg = svc.load()
    cfg.commercial.currency = "EGP"
    cfg.commercial.vat_rate = 0.14
    svc.save(cfg)

    assert user.exists()
    reloaded = svc.load()
    assert reloaded.commercial.currency == "EGP"
    assert reloaded.commercial.vat_rate == 0.14
    # untouched sections keep defaults
    assert reloaded.measurement.unit_mappings["sqm"] == "m2"


def test_partial_user_file_deep_merges_over_defaults(tmp_path):
    from app.services.rules.rules_service import RulesService

    user = tmp_path / "rules.json"
    # user only overrides one nested key
    user.write_text(json.dumps({"commercial": {"currency": "GBP"}}), encoding="utf-8")
    svc = RulesService(user_path=user)
    cfg = svc.load()
    assert cfg.commercial.currency == "GBP"
    # other commercial defaults survive the deep-merge
    assert cfg.commercial.default_payment_terms == "Net 30"
    assert cfg.commercial.markup.profit == 0.10
