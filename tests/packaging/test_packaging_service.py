import json
import pathlib

from app.schemas.rules import RulesConfig


def _rules():
    return RulesConfig.model_validate(
        json.loads(pathlib.Path("config/rules.default.json").read_text(encoding="utf-8"))
    )


async def _seed(db, trades):
    """Create a project + BOQItems with the given trade_category list."""
    from app.models.project import Project
    from app.models.boq import BOQItem

    project = Project(name="P")
    db.add(project)
    await db.flush()
    for i, trade in enumerate(trades, start=1):
        db.add(
            BOQItem(
                project_id=project.id,
                line_number=str(i),
                description=f"item {i}",
                unit="no",
                quantity=1,
                client_row_index=i,
                trade_category=trade,
                requires_review=trade is None,
            )
        )
    await db.commit()
    return project.id


async def test_generate_groups_by_trade_and_assigns_items(db_session):
    from sqlalchemy import select
    from app.models.boq import BOQItem
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["concrete", "concrete", "mep", None])

    result = await PackagingService(rules=_rules()).generate(db_session, pid)

    assert result["packages_created"] == 2          # concrete + mep
    assert result["items_assigned"] == 3
    assert result["items_unassigned"] == 1          # the None-trade item
    assert result["by_trade"]["concrete"] == 1
    assert result["by_trade"]["mep"] == 1

    packages = (await db_session.execute(
        select(Package).where(Package.project_id == pid)
    )).scalars().all()
    assert len(packages) == 2
    concrete = next(p for p in packages if p.trade_category == "concrete")
    assert concrete.total_items == 2
    assert concrete.code.startswith("PKG-")
    assert "CON" in concrete.code            # trade_abbreviations: concrete -> CON
    # items got their package_id set
    assigned = (await db_session.execute(
        select(BOQItem).where(BOQItem.trade_category == "concrete")
    )).scalars().all()
    assert all(i.package_id == concrete.id for i in assigned)


async def test_generate_splits_oversized_trade_group(db_session):
    from sqlalchemy import select
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["mep"] * 5)
    rules = _rules()
    rules.packaging.max_items_per_package = 2     # force splitting

    result = await PackagingService(rules=rules).generate(db_session, pid)

    mep_pkgs = (await db_session.execute(
        select(Package).where(Package.project_id == pid)
    )).scalars().all()
    assert len(mep_pkgs) == 3                      # ceil(5/2)
    assert result["packages_created"] == 3
    assert sum(p.total_items for p in mep_pkgs) == 5
    assert len({p.code for p in mep_pkgs}) == 3    # unique codes


async def test_generate_is_idempotent(db_session):
    from sqlalchemy import select, func
    from app.models.package import Package
    from app.services.packaging.packaging_service import PackagingService

    pid = await _seed(db_session, ["concrete", "mep"])
    svc = PackagingService(rules=_rules())
    await svc.generate(db_session, pid)
    await svc.generate(db_session, pid)            # re-run

    count = (await db_session.execute(
        select(func.count()).select_from(Package).where(Package.project_id == pid)
    )).scalar_one()
    assert count == 2                              # not duplicated
