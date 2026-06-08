from openpyxl import Workbook


def _make_boq(path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty"])
    ws.append(["1.1", "Reinforced concrete in raft", "cum", 6800])
    ws.append(["1.2", "Supply LV electrical distribution boards", "nr", 86])
    ws.append(["1.3", "Bespoke unmatched widget", "no", 3])
    wb.save(path)


def _make_blank_unit_boq(path):
    """A priced row whose unit cell is blank (lump sum / provisional sum)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty"])
    # Description + quantity present, unit cell intentionally left blank.
    ws.append(["1.1", "Provisional sum for site facilities", None, 1])
    wb.save(path)


def _rules():
    from app.schemas.rules import RulesConfig

    return RulesConfig.model_validate(
        __import__("json").loads(
            __import__("pathlib").Path("config/rules.default.json").read_text(encoding="utf-8")
        )
    )


async def test_parse_and_store_creates_classified_items(db_session, tmp_path):
    from sqlalchemy import select
    from app.models.boq import BOQItem
    from app.models.project import Project
    from app.schemas.rules import RulesConfig
    from app.services.boq.boq_service import BOQService

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()

    f = tmp_path / "boq.xlsx"
    _make_boq(f)

    result = await BOQService(rules=RulesConfig.model_validate(
        __import__("json").loads(
            __import__("pathlib").Path("config/rules.default.json").read_text(encoding="utf-8")
        )
    )).parse_and_store(db_session, project.id, str(f))

    assert result["total"] == 3
    items = (await db_session.execute(
        select(BOQItem).where(BOQItem.project_id == project.id)
    )).scalars().all()
    assert len(items) == 3
    by_desc = {i.description: i for i in items}
    assert by_desc["Reinforced concrete in raft"].trade_category == "concrete"
    assert by_desc["Supply LV electrical distribution boards"].trade_category == "mep"
    # unmatched -> no category + flagged for review
    widget = by_desc["Bespoke unmatched widget"]
    assert widget.trade_category is None
    assert widget.requires_review is True
    assert result["uncategorized"] == 1


async def test_blank_unit_row_persists(db_session, tmp_path):
    """A priced row with a blank unit cell must persist with unit=None.

    Regression: BOQItem.unit was NOT NULL, so blank-unit lines (lump sums,
    provisional sums, sub-totals) raised IntegrityError on commit.
    """
    from sqlalchemy import select
    from app.models.boq import BOQItem
    from app.models.project import Project
    from app.services.boq.boq_service import BOQService

    project = Project(name="P")
    db_session.add(project)
    await db_session.flush()

    f = tmp_path / "boq_blank_unit.xlsx"
    _make_blank_unit_boq(f)

    result = await BOQService(rules=_rules()).parse_and_store(
        db_session, project.id, str(f)
    )

    assert result["total"] == 1
    items = (await db_session.execute(
        select(BOQItem).where(BOQItem.project_id == project.id)
    )).scalars().all()
    assert len(items) == 1
    assert items[0].unit is None
