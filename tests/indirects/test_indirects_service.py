from app.schemas.rules import DurationBasedRole, RulesConfig
from app.services.indirects.indirects_service import IndirectsService


class _FakeRules:
    def __init__(self, cfg):
        self._cfg = cfg

    def load(self):
        return self._cfg


def test_compute_default_percentage_based():
    # Real RulesService loads config/rules.default.json (percentages sum to 0.085).
    out = IndirectsService().compute(22000.0)
    assert out["percentage_based"]["site_supervision"] == 660.0  # 0.03 * 22000
    assert out["percentage_based"]["temporary_works"] == 440.0  # 0.02 * 22000
    assert out["duration_based"] == {}  # default monthly_rate 0 -> dropped or zero
    assert out["location_factor"] == 1.0
    assert out["subtotal_before_location"] == 1870.0  # 0.085 * 22000
    assert out["total_indirects"] == 1870.0
    assert out["duration_months"] == 0
    assert out["location"] == "default"


def test_compute_duration_based_and_location():
    cfg = RulesConfig()
    cfg.indirects.percentage_based = {"site_supervision": 0.03}
    cfg.indirects.duration_based = {
        "project_manager": DurationBasedRole(monthly_rate=5000),
        "site_engineer": DurationBasedRole(monthly_rate=3000),
    }
    # default location_factors include remote: 1.15
    svc = IndirectsService(rules_service=_FakeRules(cfg))
    out = svc.compute(10000.0, duration_months=6, location="remote")
    assert out["percentage_based"] == {"site_supervision": 300.0}
    assert out["duration_based"] == {"project_manager": 30000.0, "site_engineer": 18000.0}
    assert out["subtotal_before_location"] == 48300.0  # 300 + 48000
    assert out["location_factor"] == 1.15
    assert out["total_indirects"] == round(48300.0 * 1.15, 2)  # 55545.0


def test_compute_unknown_location_falls_back_to_default():
    cfg = RulesConfig()
    cfg.indirects.percentage_based = {"x": 0.10}
    svc = IndirectsService(rules_service=_FakeRules(cfg))
    out = svc.compute(1000.0, location="atlantis")
    assert out["location_factor"] == 1.0  # default
    assert out["total_indirects"] == 100.0
