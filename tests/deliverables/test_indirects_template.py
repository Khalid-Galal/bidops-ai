import openpyxl
import pytest

from app.services.indirects.indirects_template import (
    detect_columns,
    populate_indirects_template,
)


def _make_template(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Indirects"
    ws.append(["Item", "Description", "Amount"])           # row 1 header
    ws.append([1, "Site Supervision", None])               # row 2
    ws.append([2, "Temporary Works", None])                # row 3
    ws.append([3, "Project Manager", None])                # row 4
    ws.append([4, "Total Indirects", "=SUM(C2:C4)"])       # row 5 formula
    wb.save(path)
    return str(path)


def test_detect_columns():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Amount"])
    label_col, amount_col = detect_columns(ws)
    assert amount_col == 3
    assert label_col == 2


def test_populate_matches_labels_and_preserves_formula(tmp_path):
    src = _make_template(tmp_path / "ind.xlsx")
    out = str(tmp_path / "out.xlsx")
    components = {
        "site_supervision": 660.0,
        "temporary_works": 440.0,
        "project_manager": 30000.0,
        "total_indirects": 31100.0,  # the Total row holds a formula -> skipped
    }
    result = populate_indirects_template(src, out, components)
    assert result["written"] == 3
    assert result["skipped_formula"] == 1
    assert result["unmatched_components"] == []
    wb = openpyxl.load_workbook(out)
    ws = wb["Indirects"]
    assert ws.cell(row=2, column=3).value == 660.0
    assert ws.cell(row=3, column=3).value == 440.0
    assert ws.cell(row=4, column=3).value == 30000.0
    assert ws.cell(row=5, column=3).value == "=SUM(C2:C4)"  # formula intact


def test_populate_reports_unmatched(tmp_path):
    src = _make_template(tmp_path / "i.xlsx")
    out = str(tmp_path / "o.xlsx")
    result = populate_indirects_template(src, out, {"helicopter_rental": 5.0})
    assert result["written"] == 0
    assert result["unmatched_components"] == ["helicopter_rental"]


def test_populate_explicit_columns(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Site Supervision", None])   # no header row at all
    p = tmp_path / "nohdr.xlsx"
    wb.save(p)
    result = populate_indirects_template(
        str(p), str(tmp_path / "o2.xlsx"), {"site_supervision": 99.0},
        amount_column=2, label_column=1,
    )
    assert result["written"] == 1


def test_populate_raises_without_amount_column(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Just", "Words"])
    p = tmp_path / "bad.xlsx"
    wb.save(p)
    with pytest.raises(ValueError):
        populate_indirects_template(str(p), str(tmp_path / "o3.xlsx"), {"x": 1.0})


import io

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ind_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.boq import BOQItem
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro")
        seed.add(project)
        await seed.flush()
        seed.add(BOQItem(project_id=project.id, line_number="1", description="AC",
                         unit="no", quantity=5, client_row_index=2, trade_category="mep",
                         unit_rate=1200, total_price=6000, currency="USD"))
        await seed.commit()
        pid = project.id

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, pid
    await client.aclose()
    app.dependency_overrides.clear()
    await engine.dispose()


def _template_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Indirects"
    ws.append(["Item", "Description", "Amount"])
    ws.append([1, "Site Supervision", None])
    ws.append([2, "Total Indirects", "=SUM(C2:C2)"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def test_populate_template_endpoint(ind_client):
    client, pid = ind_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{pid}/indirects/populate-template",
            files={"file": ("ind.xlsx", _template_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200, r.text
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        ws = wb["Indirects"]
        # site_supervision = 0.03 * 6000 = 180.0 (default rules)
        assert ws.cell(row=2, column=3).value == 180.0
        assert ws.cell(row=3, column=3).value == "=SUM(C2:C2)"  # formula intact


async def test_populate_template_rejects_non_xlsx(ind_client):
    client, pid = ind_client
    async with client as c:
        r = await c.post(
            f"/api/projects/{pid}/indirects/populate-template",
            files={"file": ("x.txt", b"nope", "text/plain")},
        )
    assert r.status_code == 400


async def test_populate_template_404_missing_project(ind_client):
    client, _ = ind_client
    async with client as c:
        r = await c.post(
            "/api/projects/999999/indirects/populate-template",
            files={"file": ("i.xlsx", _template_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 404
