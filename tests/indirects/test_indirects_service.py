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


import pytest

from app.models.boq import BOQItem
from app.models.project import Project
from app.services.indirects.indirects_service import IndirectsService as _IS


async def _seed_priced_project(db):
    project = Project(name="Metro")
    db.add(project)
    await db.flush()
    # Two priced items totalling 22000, one excluded item that must NOT count.
    db.add_all([
        BOQItem(project_id=project.id, line_number="1", description="AC unit",
                unit="no", quantity=5, client_row_index=2, trade_category="mep",
                unit_rate=1200, total_price=6000, currency="USD"),
        BOQItem(project_id=project.id, line_number="2", description="VRF",
                unit="no", quantity=2, client_row_index=3, trade_category="mep",
                unit_rate=8000, total_price=16000, currency="USD"),
        BOQItem(project_id=project.id, line_number="3", description="Excluded",
                unit="no", quantity=1, client_row_index=4, trade_category="mep",
                unit_rate=999, total_price=999, currency="USD", is_excluded=True),
    ])
    await db.commit()
    return project.id


async def test_indirects_result_uses_direct_cost(db_session):
    pid = await _seed_priced_project(db_session)
    out = await _IS().indirects_result(db_session, pid)
    assert out["direct_cost"] == 22000.0  # excluded item not counted
    assert out["currency"] == "USD"
    assert out["indirects"]["total_indirects"] == 1870.0  # 0.085 * 22000


async def test_project_cost_summary_rolls_up_indirects_then_markups(db_session):
    pid = await _seed_priced_project(db_session)
    out = await _IS().project_cost_summary(db_session, pid)
    assert out["direct_cost"] == 22000.0
    assert out["indirects"]["total_indirects"] == 1870.0
    assert out["total_cost_base"] == 23870.0  # direct + indirects
    # markups on 23870: overhead .08, profit .10, contingency .05, risk .03 -> .26
    assert out["markups"]["markup_total"] == round(23870.0 * 0.26, 2)  # 6206.2
    assert out["selling_before_vat"] == round(23870.0 * 1.26, 2)  # 30076.2
    assert out["grand_total"] == round(23870.0 * 1.26, 2)  # vat 0
    assert out["currency"] == "USD"
