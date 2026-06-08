def test_classify_uses_rules_trade_categories():
    from app.services.boq.trade_classifier import classify_trade
    from app.schemas.rules import RulesConfig

    rules = RulesConfig.model_validate(
        __import__("json").loads(
            __import__("pathlib").Path("config/rules.default.json").read_text(encoding="utf-8")
        )
    )

    cat, conf = classify_trade("Reinforced concrete C35/45 in columns", rules)
    assert cat == "concrete" and conf > 0

    cat, conf = classify_trade("Supply and install HVAC ductwork", rules)
    assert cat == "mep"

    cat, conf = classify_trade("Excavation in all types of soil", rules)
    assert cat == "civil"

    cat, conf = classify_trade("Internal painting to walls", rules)
    assert cat == "finishes"

    cat, conf = classify_trade("Bespoke unmatched widget assembly", rules)
    assert cat is None and conf == 0.0
