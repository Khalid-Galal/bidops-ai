# Phase 6C-lite — Workbench UI (Jinja) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every v2 backend capability drivable from the browser: a per-project tabbed **Workbench** page (BOQ, Packages, RFQ, Offers, Pricing, Cost, Historical, Deliverables) plus a global **Suppliers** page — all server-rendered Jinja with inline vanilla-JS `fetch` against the existing JSON API, exactly the v1 `project.html` pattern.

**Architecture:** One shell template (`workbench.html`) provides shared JS helpers (`api`, `esc`, `tbl`, `showTab`) and auto-builds the tab nav from `<section class="wb-tab" data-label=...>` elements; each tab lives in its own Jinja include (`app/templates/workbench/_*.html`) containing its markup AND its `<script>` (loader + button handlers). No new JS frameworks, no Node — the API stays the single source of truth; the UI only orchestrates existing endpoints. File-returning POSTs (template population) use plain HTML multipart forms so the browser handles the download natively. Tests are smoke tests (page renders, key markers present) — API behavior is already covered by 259 tests.

**Tech Stack:** Jinja2 (existing `templates` engine) · vanilla JS `fetch` · existing CSS classes (`.btn .btn-primary .btn-secondary .card .badge .action-bar`) · pytest-asyncio + httpx ASGITransport (smoke tests).

**No database migration, no new Python services.** Only `app/api/pages.py` gains two routes.

---

## Pre-flight (read, do not skip)

1. **TemplateResponse signature:** ALWAYS `templates.TemplateResponse(request, "name.html", ctx)` — the legacy `(name, {"request": ...})` style crashes on the installed Starlette (fixed in Phase 14; do not regress).
2. **The v1 JS pattern** is inline `<script>` with `fetch` (see `app/templates/project.html`). Follow it; no build step.
3. **Existing endpoints only.** Every button maps to an endpoint that already exists and is tested. Exact paths are embedded in the code below — do not invent new ones.
4. **Multipart via JS:** use `FormData`; do NOT set `Content-Type` manually. For endpoints that RETURN a file (pricing/indirects template fill), use a plain `<form method="post" enctype="multipart/form-data">` so the browser downloads the `FileResponse`.
5. **Jinja autoescape is on** for `.html` templates; in JS we escape API data with the shared `esc()` before inserting via `innerHTML`.
6. **`base.html`** has blocks `title`, `content`, `scripts`. Page routes live in `app/api/pages.py` (no `/api` prefix) and import `templates` from `app.main`.
7. Run the whole suite after **every** task: `.venv/Scripts/python.exe -m pytest tests/ -q` (baseline = **259 passing**).

---

## File Structure

**Create:**
- `app/templates/suppliers.html`
- `app/templates/workbench.html` (shell: helpers + nav + includes)
- `app/templates/workbench/_boq.html`, `_packages.html`, `_rfq.html`, `_offers.html`, `_pricing.html`, `_cost.html`, `_historical.html`, `_deliverables.html`
- `tests/ui/__init__.py`, `tests/ui/test_pages.py`

**Modify:**
- `app/api/pages.py` — `GET /suppliers`, `GET /projects/{id}/workbench`.
- `app/templates/base.html` — add Suppliers nav link.
- `app/templates/project.html` — action-bar links to Dashboard/Workbench.
- `app/templates/dashboard.html` — link to Workbench.

---

## Task 1: Routes, nav links, Suppliers page

**Files:**
- Create: `app/templates/suppliers.html`, `tests/ui/__init__.py`, `tests/ui/test_pages.py`
- Modify: `app/api/pages.py`, `app/templates/base.html`, `app/templates/project.html`, `app/templates/dashboard.html`

- [ ] **Step 1: Write the failing smoke tests**

Create `tests/ui/__init__.py` (empty file).

Create `tests/ui/test_pages.py`:

```python
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def ui_client():
    from app.database import get_db
    from app.main import app
    from app.models import Base
    from app.models.project import Project

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as seed:
        project = Project(name="Metro UI")
        seed.add(project)
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


async def test_suppliers_page_renders(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/suppliers")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Suppliers" in r.text
        assert "supplier-add-form" in r.text


async def test_base_nav_has_suppliers_link(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/")
        assert 'href="/suppliers"' in r.text


async def test_project_page_links_to_workbench(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}")
        assert f'href="/projects/{pid}/workbench"' in r.text
        assert f'href="/projects/{pid}/dashboard"' in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q`
Expected: FAIL — `/suppliers` 404, missing links.

- [ ] **Step 3: Add the routes to `app/api/pages.py`**

Append:

```python
@router.get("/suppliers")
async def suppliers_page(request: Request):
    """Render the global supplier database page (data loads via the JSON API)."""
    return templates.TemplateResponse(request, "suppliers.html", {})


@router.get("/projects/{project_id}/workbench")
async def workbench_page(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render the tabbed v2 workbench for one project."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return templates.TemplateResponse(request, "workbench.html", {"project": project})
```

- [ ] **Step 4: Nav + cross-links**

In `app/templates/base.html`, change the `<nav>` block to:

```html
            <nav>
                <a href="/">Projects</a>
                <a href="/suppliers">Suppliers</a>
                <a href="/docs" target="_blank">API Docs</a>
            </nav>
```

In `app/templates/project.html`, insert immediately after the `{% block content %}` line:

```html
<p class="action-bar">
  <a class="btn btn-secondary" href="/projects/{{ project.id }}/dashboard">Dashboard</a>
  <a class="btn btn-secondary" href="/projects/{{ project.id }}/workbench">Workbench</a>
</p>
```

In `app/templates/dashboard.html`, insert immediately after the `<h1>...</h1>` line:

```html
<p class="action-bar">
  <a class="btn btn-secondary" href="/projects/{{ d.project.id }}">Documents</a>
  <a class="btn btn-secondary" href="/projects/{{ d.project.id }}/workbench">Workbench</a>
</p>
```

- [ ] **Step 5: Create `app/templates/suppliers.html`**

```html
{% extends "base.html" %}
{% block title %}Suppliers | BidOps AI{% endblock %}
{% block content %}
<h1>Suppliers</h1>
<p class="action-bar">
  <a class="btn btn-secondary" href="/api/suppliers/export">Export Excel</a>
</p>

<div class="card">
  <h3>Add supplier</h3>
  <form id="supplier-add-form">
    <input name="name" placeholder="Name" required>
    <input name="emails" placeholder="Emails (comma-separated)">
    <input name="trades" placeholder="Trades (comma-separated, e.g. mep,civil)">
    <input name="contact_name" placeholder="Contact name">
    <button class="btn btn-primary" type="submit">Add</button>
  </form>
</div>

<div class="card">
  <h3>Import from Excel</h3>
  <form id="supplier-import-form">
    <input type="file" name="file" accept=".xlsx" required>
    <button class="btn btn-secondary" type="submit">Import</button>
    <span id="import-result"></span>
  </form>
</div>

<div class="card">
  <h3>Supplier list</h3>
  <input id="trade-filter" placeholder="Filter by trade (e.g. mep)">
  <button class="btn btn-secondary" id="reload-btn" type="button">Reload</button>
  <div id="supplier-table"></div>
</div>
{% endblock %}

{% block scripts %}
<script>
function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
async function api(path, opts) {
  const resp = await fetch(path, opts || {});
  if (!resp.ok) {
    let detail = resp.status;
    try { detail = (await resp.json()).detail || detail; } catch (e) {}
    alert('Error: ' + detail);
    throw new Error(String(detail));
  }
  return resp.status === 204 ? null : resp.json();
}

async function loadSuppliers() {
  const trade = document.getElementById('trade-filter').value.trim();
  const qs = trade ? ('?trade=' + encodeURIComponent(trade)) : '';
  const rows = await api('/api/suppliers' + qs);
  let html = '<table><tr><th>Code</th><th>Name</th><th>Emails</th><th>Trades</th>'
    + '<th>Rating</th><th>RFQs</th><th>Offers</th><th></th></tr>';
  for (const s of rows) {
    html += '<tr><td>' + esc(s.code) + '</td><td>' + esc(s.name) + '</td><td>'
      + esc((s.emails || []).join(', ')) + '</td><td>'
      + esc((s.trade_categories || []).join(', ')) + '</td><td>'
      + esc(s.rating) + '</td><td>' + esc(s.total_rfqs_sent) + '</td><td>'
      + esc(s.total_offers_received) + '</td><td>'
      + '<button class="btn btn-secondary" onclick="blacklistSupplier(' + s.id + ')">Blacklist</button>'
      + '</td></tr>';
  }
  html += '</table>';
  document.getElementById('supplier-table').innerHTML = html;
}

async function blacklistSupplier(id) {
  const reason = prompt('Blacklist reason?');
  if (!reason) return;
  await api('/api/suppliers/' + id + '/blacklist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason }),
  });
  loadSuppliers();
}

document.getElementById('supplier-add-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const f = e.target;
  await api('/api/suppliers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: f.name.value,
      emails: f.emails.value.split(',').map(s => s.trim()).filter(Boolean),
      trade_categories: f.trades.value.split(',').map(s => s.trim()).filter(Boolean),
      contact_name: f.contact_name.value || null,
    }),
  });
  f.reset();
  loadSuppliers();
});

document.getElementById('supplier-import-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const result = await api('/api/suppliers/import', { method: 'POST', body: fd });
  document.getElementById('import-result').textContent =
    'imported ' + result.imported + ', updated ' + result.updated + ', skipped ' + result.skipped;
  loadSuppliers();
});

document.getElementById('reload-btn').addEventListener('click', loadSuppliers);
loadSuppliers();
</script>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q`
Expected: PASS (3 tests). (The workbench link test passes because `project.html` now has the link; the workbench ROUTE 404s until Task 2 — that's fine, the test only checks the link.)

Then run the FULL suite: `.venv/Scripts/python.exe -m pytest tests/ -q` — all green.

- [ ] **Step 7: Commit**

```bash
git add app/api/pages.py app/templates/base.html app/templates/project.html app/templates/dashboard.html app/templates/suppliers.html tests/ui/
git commit -m "feat(phase-6c): suppliers page + nav/cross links + page routes"
```

---

## Task 2: Workbench shell + BOQ + Packages tabs

**Files:**
- Create: `app/templates/workbench.html`, `app/templates/workbench/_boq.html`, `app/templates/workbench/_packages.html`
- Test: `tests/ui/test_pages.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_pages.py`:

```python
async def test_workbench_renders_with_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert r.status_code == 200
        assert "Metro UI" in r.text
        assert 'id="tab-boq"' in r.text
        assert 'id="tab-packages"' in r.text


async def test_workbench_404_missing_project(ui_client):
    client, _ = ui_client
    async with client as c:
        r = await c.get("/projects/999999/workbench")
    assert r.status_code == 404
```

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q -k workbench`
Expected: FAIL — `workbench.html` template missing (500/TemplateNotFound).

- [ ] **Step 2: Create the shell `app/templates/workbench.html`**

```html
{% extends "base.html" %}
{% block title %}{{ project.name }} — Workbench | BidOps AI{% endblock %}
{% block content %}
<h1>Workbench — {{ project.name }}</h1>
<p class="action-bar">
  <a class="btn btn-secondary" href="/projects/{{ project.id }}">Documents</a>
  <a class="btn btn-secondary" href="/projects/{{ project.id }}/dashboard">Dashboard</a>
</p>

<div id="wb-nav" class="action-bar"></div>

{% include "workbench/_boq.html" %}
{% include "workbench/_packages.html" %}
{% endblock %}

{% block scripts %}
<script>
const PID = {{ project.id }};

function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function api(path, opts) {
  const resp = await fetch(path, opts || {});
  if (!resp.ok) {
    let detail = resp.status;
    try { detail = (await resp.json()).detail || detail; } catch (e) {}
    alert('Error: ' + detail);
    throw new Error(String(detail));
  }
  return resp.status === 204 ? null : resp.json();
}

function postJSON(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

/* tbl(['H1','H2'], [[a,b],[c,d]]) -> escaped HTML table string */
function tbl(headers, rows) {
  let html = '<table><tr>';
  for (const h of headers) html += '<th>' + esc(h) + '</th>';
  html += '</tr>';
  for (const row of rows) {
    html += '<tr>';
    for (const cell of row) {
      /* cells beginning with !html: are trusted button markup built locally */
      if (typeof cell === 'string' && cell.indexOf('!html:') === 0) {
        html += '<td>' + cell.slice(6) + '</td>';
      } else {
        html += '<td>' + esc(cell) + '</td>';
      }
    }
    html += '</tr>';
  }
  return html + '</table>';
}

function showTab(name) {
  document.querySelectorAll('.wb-tab').forEach(function (s) {
    s.style.display = (s.id === 'tab-' + name) ? '' : 'none';
  });
  document.querySelectorAll('#wb-nav button').forEach(function (b) {
    b.className = (b.dataset.tab === name) ? 'btn btn-primary' : 'btn btn-secondary';
  });
  location.hash = name;
  const loader = window['load_' + name];
  if (typeof loader === 'function') loader().catch(function () {});
}

document.addEventListener('DOMContentLoaded', function () {
  const nav = document.getElementById('wb-nav');
  document.querySelectorAll('.wb-tab').forEach(function (s) {
    const name = s.id.replace('tab-', '');
    const b = document.createElement('button');
    b.dataset.tab = name;
    b.textContent = s.dataset.label || name;
    b.className = 'btn btn-secondary';
    b.addEventListener('click', function () { showTab(name); });
    nav.appendChild(b);
  });
  const initial = (location.hash || '#boq').slice(1);
  showTab(document.getElementById('tab-' + initial) ? initial : 'boq');
});
</script>
{% endblock %}
```

- [ ] **Step 3: Create `app/templates/workbench/_boq.html`**

```html
<section id="tab-boq" class="wb-tab" data-label="BOQ" style="display:none">
  <div class="card">
    <h3>Parse BOQ workbook</h3>
    <form id="boq-parse-form">
      <input type="file" name="file" accept=".xlsx,.xls" required>
      <button class="btn btn-primary" type="submit">Parse + classify</button>
      <span id="boq-parse-result"></span>
    </form>
  </div>
  <div class="card">
    <h3>BOQ items</h3>
    <div id="boq-table"></div>
  </div>
</section>
<script>
window.load_boq = async function () {
  const items = await api('/api/projects/' + PID + '/boq');
  document.getElementById('boq-table').innerHTML = tbl(
    ['#', 'Description', 'Unit', 'Qty', 'Trade', 'Conf.', 'Rate', 'Total', ''],
    items.map(function (i) {
      return [i.line_number, i.description, i.unit, i.quantity, i.trade_category,
        i.classification_confidence,
        i.unit_rate === undefined ? '' : i.unit_rate,
        i.total_price === undefined ? '' : i.total_price,
        '!html:<button class="btn btn-secondary" onclick="setRate(' + i.id + ')">Set rate</button>'];
    })
  );
};

async function setRate(itemId) {
  const rate = prompt('Unit rate?');
  if (!rate) return;
  await api('/api/boq-items/' + itemId + '/price', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unit_rate: parseFloat(rate), notes: 'manual via workbench' }),
  });
  window.load_boq();
}

document.getElementById('boq-parse-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const r = await api('/api/projects/' + PID + '/boq/parse', { method: 'POST', body: fd });
  document.getElementById('boq-parse-result').textContent =
    r.total + ' rows, ' + r.classified + ' classified, ' + r.uncategorized + ' uncategorized';
  window.load_boq();
});
</script>
```

> Note: `BOQItemResponse` does not include `unit_rate`/`total_price` fields — the map above tolerates `undefined` and shows blank. The "Set rate" PATCH returns the priced item; the reload shows trade/qty as before. This is acceptable; pricing detail lives in the Pricing tab.

- [ ] **Step 4: Create `app/templates/workbench/_packages.html`**

```html
<section id="tab-packages" class="wb-tab" data-label="Packages" style="display:none">
  <p class="action-bar">
    <button class="btn btn-primary" onclick="pkgAction('generate')">Generate packages</button>
    <button class="btn btn-secondary" onclick="pkgAction('link-documents')">Link documents</button>
    <button class="btn btn-secondary" onclick="pkgAction('export')">Export folders + register</button>
    <a class="btn btn-secondary" href="/api/projects/{{ project.id }}/packages/register">Download register</a>
  </p>
  <div class="card">
    <h3>Packages</h3>
    <div id="pkg-table"></div>
  </div>
  <div class="card" id="pkg-detail" style="display:none">
    <h3 id="pkg-detail-title"></h3>
    <div id="pkg-detail-body"></div>
  </div>
</section>
<script>
window.load_packages = async function () {
  const pkgs = await api('/api/projects/' + PID + '/packages');
  document.getElementById('pkg-table').innerHTML = tbl(
    ['Code', 'Name', 'Trade', 'Status', 'Items', ''],
    pkgs.map(function (p) {
      return [p.code, p.name, p.trade_category, p.status, p.total_items,
        '!html:<button class="btn btn-secondary" onclick="pkgDetail(' + p.id + ')">Detail</button>'];
    })
  );
};

async function pkgAction(action) {
  const r = await postJSON('/api/projects/' + PID + '/packages/' + action);
  alert(JSON.stringify(r));
  window.load_packages();
}

async function pkgDetail(pkgId) {
  const d = await api('/api/projects/' + PID + '/packages/' + pkgId);
  document.getElementById('pkg-detail-title').textContent = d.code + ' — ' + d.name;
  document.getElementById('pkg-detail-body').innerHTML =
    '<h4>Items</h4>' + tbl(['#', 'Description', 'Unit', 'Qty'],
      d.items.map(function (i) { return [i.line_number, i.description, i.unit, i.quantity]; }))
    + '<h4>Linked documents</h4>' + tbl(['Document', 'Score', 'Reason'],
      d.linked_documents.map(function (l) { return [l.filename, l.relevance_score, l.relevance_reason]; }));
  document.getElementById('pkg-detail').style.display = '';
}
</script>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q`
Expected: PASS (5 tests). Full suite green.

- [ ] **Step 6: Commit**

```bash
git add app/templates/workbench.html app/templates/workbench/_boq.html app/templates/workbench/_packages.html tests/ui/test_pages.py
git commit -m "feat(phase-6c): workbench shell + BOQ and Packages tabs"
```

---

## Task 3: RFQ + Offers tabs

**Files:**
- Create: `app/templates/workbench/_rfq.html`, `app/templates/workbench/_offers.html`
- Modify: `app/templates/workbench.html` (add includes)
- Test: `tests/ui/test_pages.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_pages.py`:

```python
async def test_workbench_has_rfq_and_offers_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-rfq"' in r.text
        assert 'id="tab-offers"' in r.text
```

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q -k rfq`
Expected: FAIL.

- [ ] **Step 2: Add includes to `app/templates/workbench.html`**

After the `_packages.html` include line, add:

```html
{% include "workbench/_rfq.html" %}
{% include "workbench/_offers.html" %}
```

- [ ] **Step 3: Create `app/templates/workbench/_rfq.html`**

```html
<section id="tab-rfq" class="wb-tab" data-label="RFQ" style="display:none">
  <div class="card">
    <h3>Create RFQ drafts</h3>
    <label>Package: <select id="rfq-pkg"></select></label>
    <button class="btn btn-secondary" onclick="loadSuggested()">Suggested suppliers</button>
    <div id="rfq-suggested"></div>
    <button class="btn btn-primary" onclick="createRfq()">Create drafts for checked suppliers</button>
  </div>
  <div class="card">
    <h3>Email log</h3>
    <button class="btn btn-secondary" onclick="loadEmails()">Reload</button>
    <div id="email-table"></div>
  </div>
  <div class="card" id="email-preview" style="display:none">
    <h3 id="email-subject"></h3>
    <div id="email-body"></div>
  </div>
</section>
<script>
window.load_rfq = async function () {
  const pkgs = await api('/api/projects/' + PID + '/packages');
  const sel = document.getElementById('rfq-pkg');
  sel.innerHTML = pkgs.map(function (p) {
    return '<option value="' + p.id + '">' + esc(p.code) + ' — ' + esc(p.name) + '</option>';
  }).join('');
  await loadEmails();
};

async function loadSuggested() {
  const pkgId = document.getElementById('rfq-pkg').value;
  if (!pkgId) { alert('Generate packages first'); return; }
  const sups = await api('/api/projects/' + PID + '/packages/' + pkgId + '/suggested-suppliers');
  document.getElementById('rfq-suggested').innerHTML = sups.length
    ? sups.map(function (s) {
        return '<label style="display:block"><input type="checkbox" class="rfq-sup" value="' + s.id + '"> '
          + esc(s.name) + ' (' + esc((s.emails || []).join(', ')) + ')</label>';
      }).join('')
    : '<p>No matching suppliers — add some on the Suppliers page.</p>';
}

async function createRfq() {
  const pkgId = document.getElementById('rfq-pkg').value;
  const ids = Array.from(document.querySelectorAll('.rfq-sup:checked')).map(function (c) {
    return parseInt(c.value, 10);
  });
  if (!pkgId || !ids.length) { alert('Pick a package and at least one supplier'); return; }
  const r = await postJSON('/api/projects/' + PID + '/packages/' + pkgId + '/rfq',
    { supplier_ids: ids });
  alert('Drafts created: ' + r.drafts_created
    + (r.skipped.length ? ('; skipped: ' + r.skipped.join('; ')) : ''));
  loadEmails();
}

async function loadEmails() {
  const pkgId = document.getElementById('rfq-pkg').value;
  const qs = pkgId ? ('?package_id=' + pkgId) : '';
  const emails = await api('/api/emails' + qs);
  document.getElementById('email-table').innerHTML = tbl(
    ['ID', 'Type', 'Status', 'To', 'Subject', ''],
    emails.map(function (m) {
      return [m.id, m.email_type, m.status, (m.to || []).join(', '), m.subject,
        '!html:<button class="btn btn-secondary" onclick="previewEmail(' + m.id + ')">Preview</button> '
        + '<button class="btn btn-primary" onclick="sendEmail(' + m.id + ')">Send</button>'];
    })
  );
}

async function previewEmail(id) {
  const m = await api('/api/emails/' + id);
  document.getElementById('email-subject').textContent = m.subject + ' → ' + (m.to || []).join(', ');
  /* body_html is server-generated template output; render it in the preview pane */
  document.getElementById('email-body').innerHTML = m.body_html;
  document.getElementById('email-preview').style.display = '';
}

async function sendEmail(id) {
  if (!confirm('Send this email now via SMTP?')) return;
  const r = await postJSON('/api/emails/' + id + '/send');
  alert('Status: ' + r.status + (r.error ? (' — ' + r.error) : ''));
  loadEmails();
}
</script>
```

- [ ] **Step 4: Create `app/templates/workbench/_offers.html`**

```html
<section id="tab-offers" class="wb-tab" data-label="Offers" style="display:none">
  <div class="card">
    <h3>Ingest offer</h3>
    <form id="offer-ingest-form">
      <label>Package: <select id="offer-pkg"></select></label>
      <input name="supplier_id" placeholder="Supplier ID" required size="10">
      <input type="file" name="files" multiple required>
      <button class="btn btn-primary" type="submit">Upload offer</button>
    </form>
  </div>
  <div class="card">
    <h3>Offers
      <button class="btn btn-secondary" onclick="loadOffers()">Reload</button>
      <button class="btn btn-primary" onclick="scoreOffers()">Score + rank</button>
      <button class="btn btn-secondary" onclick="loadComparison()">Comparison</button>
      <a class="btn btn-secondary" id="cmp-xlsx" href="#">Comparison.xlsx</a>
    </h3>
    <div id="offer-table"></div>
    <div id="cmp-table"></div>
  </div>
</section>
<script>
window.load_offers = async function () {
  const pkgs = await api('/api/projects/' + PID + '/packages');
  const sel = document.getElementById('offer-pkg');
  sel.innerHTML = pkgs.map(function (p) {
    return '<option value="' + p.id + '">' + esc(p.code) + '</option>';
  }).join('');
  sel.onchange = loadOffers;
  if (pkgs.length) await loadOffers();
};

function offerPkgId() { return document.getElementById('offer-pkg').value; }

async function loadOffers() {
  const pkgId = offerPkgId();
  if (!pkgId) return;
  document.getElementById('cmp-xlsx').href =
    '/api/projects/' + PID + '/packages/' + pkgId + '/offers/comparison.xlsx';
  const offers = await api('/api/projects/' + PID + '/packages/' + pkgId + '/offers');
  document.getElementById('offer-table').innerHTML = tbl(
    ['ID', 'Supplier', 'Status', 'Price', 'Ccy', 'Score', 'Rank', ''],
    offers.map(function (o) {
      return [o.id, o.supplier_id, o.status, o.total_price, o.currency,
        o.overall_score, o.rank,
        '!html:'
        + '<button class="btn btn-secondary" onclick="offerAct(' + o.id + ',\'extract\')">Extract</button> '
        + '<button class="btn btn-secondary" onclick="offerAct(' + o.id + ',\'check-compliance\')">Compliance</button> '
        + '<button class="btn btn-primary" onclick="offerAct(' + o.id + ',\'select\')">Select</button> '
        + '<button class="btn btn-secondary" onclick="clarify(' + o.id + ')">Clarify</button>'];
    })
  );
}

async function offerAct(id, action) {
  const r = await postJSON('/api/offers/' + id + '/' + action);
  alert(action + ': ' + (r.status || 'ok'));
  loadOffers();
}

async function clarify(id) {
  const item = prompt('Clarification item (one line)?');
  if (!item) return;
  await postJSON('/api/offers/' + id + '/clarification', { items: [item] });
  alert('Clarification draft created — see RFQ tab email log.');
}

async function scoreOffers() {
  const r = await postJSON('/api/projects/' + PID + '/packages/' + offerPkgId() + '/offers/score');
  alert('Scored ' + r.offers_scored + ' offers');
  loadOffers();
}

async function loadComparison() {
  const c = await api('/api/projects/' + PID + '/packages/' + offerPkgId() + '/offers/comparison');
  document.getElementById('cmp-table').innerHTML =
    '<h4>' + esc(c.package_name) + ' — ' + c.total_offers + ' offers, min '
    + esc(c.price_min) + ' ' + esc(c.currency) + '</h4>'
    + tbl(['Rank', 'Supplier', 'Price', 'Validity', 'Delivery', 'Overall'],
        c.offers.map(function (o) {
          return [o.rank, o.supplier_name, o.total_price, o.validity_days,
            o.delivery_weeks, o.overall_score];
        }));
}

document.getElementById('offer-ingest-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const fd = new FormData();
  fd.append('supplier_id', e.target.supplier_id.value);
  for (const f of e.target.files.files) fd.append('files', f);
  await api('/api/projects/' + PID + '/packages/' + offerPkgId() + '/offers',
    { method: 'POST', body: fd });
  loadOffers();
});
</script>
```

- [ ] **Step 5: Run tests; commit**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q` → PASS (6). Full suite green.

```bash
git add app/templates/workbench.html app/templates/workbench/_rfq.html app/templates/workbench/_offers.html tests/ui/test_pages.py
git commit -m "feat(phase-6c): RFQ and Offers workbench tabs"
```

---

## Task 4: Pricing + Cost tabs

**Files:**
- Create: `app/templates/workbench/_pricing.html`, `app/templates/workbench/_cost.html`
- Modify: `app/templates/workbench.html` (add includes)
- Test: `tests/ui/test_pages.py` (append)

- [ ] **Step 1: Failing test**

Append to `tests/ui/test_pages.py`:

```python
async def test_workbench_has_pricing_and_cost_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-pricing"' in r.text
        assert 'id="tab-cost"' in r.text
```

Run + expect FAIL. Then add to `workbench.html` after the `_offers.html` include:

```html
{% include "workbench/_pricing.html" %}
{% include "workbench/_cost.html" %}
```

- [ ] **Step 2: Create `app/templates/workbench/_pricing.html`**

```html
<section id="tab-pricing" class="wb-tab" data-label="Pricing" style="display:none">
  <div class="card">
    <h3>Populate prices from a selected offer</h3>
    <input id="pop-offer-id" placeholder="Offer ID (must be Selected)" size="14">
    <button class="btn btn-primary" onclick="populatePrices()">Populate</button>
    <span id="pop-result"></span>
  </div>
  <div class="card">
    <h3>Pricing summary <button class="btn btn-secondary" onclick="window.load_pricing()">Reload</button></h3>
    <div id="pricing-summary"></div>
  </div>
  <div class="card">
    <h3>Gaps</h3>
    <div id="pricing-gaps"></div>
  </div>
  <div class="card">
    <h3>Fill client BOQ template (formula-preserving)</h3>
    <form method="post" enctype="multipart/form-data"
          action="/api/projects/{{ project.id }}/pricing/populate-template">
      <input type="file" name="file" accept=".xlsx" required>
      <button class="btn btn-primary" type="submit">Fill + download</button>
    </form>
  </div>
</section>
<script>
window.load_pricing = async function () {
  const s = await api('/api/projects/' + PID + '/pricing/summary');
  document.getElementById('pricing-summary').innerHTML = tbl(
    ['Direct cost', 'Markup total', 'Selling', 'VAT', 'Grand total', 'Ccy', 'Done'],
    [[s.cost_subtotal, s.markups.markup_total, s.selling_before_vat,
      s.vat_amount, s.grand_total, s.currency, s.completion_rate + '%']]
  ) + '<h4>By trade</h4>' + tbl(['Trade', 'Items', 'Total', '%'],
    s.by_trade.map(function (t) { return [t.trade, t.count, t.total, t.percentage]; }));

  const g = await api('/api/projects/' + PID + '/pricing/gaps');
  document.getElementById('pricing-gaps').innerHTML =
    '<p>Unpriced: ' + g.unpriced_count + ' · Needs review: ' + g.needs_review_count
    + ' · Excluded: ' + g.excluded_count + '</p>'
    + tbl(['#', 'Description', 'Reason'],
        g.unpriced.concat(g.needs_review).map(function (i) {
          return [i.line_number, i.description, i.reason];
        }));
};

async function populatePrices() {
  const id = document.getElementById('pop-offer-id').value;
  if (!id) return;
  const r = await postJSON('/api/offers/' + id + '/populate-prices');
  document.getElementById('pop-result').textContent =
    r.items_populated + ' priced, ' + r.items_unmatched + ' unmatched ('
    + r.items_needs_review + ' need review)';
  window.load_pricing();
}
</script>
```

- [ ] **Step 3: Create `app/templates/workbench/_cost.html`**

```html
<section id="tab-cost" class="wb-tab" data-label="Cost" style="display:none">
  <div class="card">
    <h3>Project cost rollup</h3>
    <label>Duration (months): <input id="cost-months" type="number" min="0" value="0" size="6"></label>
    <label>Location: <input id="cost-location" value="default" size="12"></label>
    <button class="btn btn-primary" onclick="window.load_cost()">Compute</button>
    <div id="cost-summary"></div>
  </div>
  <div class="card">
    <h3>Fill client indirects template (formula-preserving)</h3>
    <form id="ind-template-form" method="post" enctype="multipart/form-data" action="#">
      <input type="file" name="file" accept=".xlsx" required>
      <button class="btn btn-primary" type="submit">Fill + download</button>
    </form>
  </div>
</section>
<script>
window.load_cost = async function () {
  const months = document.getElementById('cost-months').value || 0;
  const loc = document.getElementById('cost-location').value || 'default';
  const c = await api('/api/projects/' + PID + '/cost-summary?duration_months='
    + encodeURIComponent(months) + '&location=' + encodeURIComponent(loc));
  const ind = c.indirects;
  let breakdown = Object.entries(ind.percentage_based)
    .concat(Object.entries(ind.duration_based))
    .map(function (kv) { return [kv[0].replace(/_/g, ' '), kv[1]]; });
  document.getElementById('cost-summary').innerHTML = tbl(
    ['Direct', 'Indirects', 'Cost base', 'Markups', 'Selling', 'VAT', 'GRAND TOTAL', 'Ccy'],
    [[c.direct_cost, ind.total_indirects, c.total_cost_base, c.markups.markup_total,
      c.selling_before_vat, c.vat_amount, c.grand_total, c.currency]]
  ) + '<h4>Indirects breakdown (×' + ind.location_factor + ' location factor)</h4>'
    + tbl(['Component', 'Amount'], breakdown);
};

document.getElementById('ind-template-form').addEventListener('submit', function (e) {
  /* set query params from the inputs at submit time, then let the browser POST */
  const months = document.getElementById('cost-months').value || 0;
  const loc = document.getElementById('cost-location').value || 'default';
  e.target.action = '/api/projects/' + PID + '/indirects/populate-template?duration_months='
    + encodeURIComponent(months) + '&location=' + encodeURIComponent(loc);
});
</script>
```

- [ ] **Step 4: Run tests; commit**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q` → PASS (7). Full suite green.

```bash
git add app/templates/workbench.html app/templates/workbench/_pricing.html app/templates/workbench/_cost.html tests/ui/test_pages.py
git commit -m "feat(phase-6c): Pricing and Cost workbench tabs"
```

---

## Task 5: Historical + Deliverables tabs

**Files:**
- Create: `app/templates/workbench/_historical.html`, `app/templates/workbench/_deliverables.html`
- Modify: `app/templates/workbench.html` (add includes)
- Test: `tests/ui/test_pages.py` (append)

- [ ] **Step 1: Failing test**

Append to `tests/ui/test_pages.py`:

```python
async def test_workbench_has_historical_and_deliverables_tabs(ui_client):
    client, pid = ui_client
    async with client as c:
        r = await c.get(f"/projects/{pid}/workbench")
        assert 'id="tab-historical"' in r.text
        assert 'id="tab-deliverables"' in r.text
```

Run + expect FAIL. Then add to `workbench.html` after the `_cost.html` include:

```html
{% include "workbench/_historical.html" %}
{% include "workbench/_deliverables.html" %}
```

- [ ] **Step 2: Create `app/templates/workbench/_historical.html`**

```html
<section id="tab-historical" class="wb-tab" data-label="Historical" style="display:none">
  <p class="action-bar">
    <button class="btn btn-secondary" onclick="indexProject()">Index this project's prices</button>
    <button class="btn btn-primary" onclick="loadSuggestions()">Suggest prices for unpriced items</button>
  </p>
  <div class="card">
    <h3>Import historical rate sheet</h3>
    <form id="hist-import-form">
      <input type="file" name="file" accept=".xlsx" required>
      <button class="btn btn-secondary" type="submit">Import</button>
      <span id="hist-import-result"></span>
    </form>
  </div>
  <div class="card">
    <h3>Suggestions</h3>
    <div id="hist-suggestions"></div>
  </div>
</section>
<script>
window.load_historical = async function () { /* loads on demand via buttons */ };

async function indexProject() {
  const r = await postJSON('/api/projects/' + PID + '/historical/index');
  alert('Indexed ' + r.indexed + ' priced items into the corpus');
}

async function loadSuggestions() {
  const s = await api('/api/projects/' + PID + '/historical/suggestions?only_unpriced=true');
  document.getElementById('hist-suggestions').innerHTML = tbl(
    ['#', 'Description', 'Suggested', 'Range', 'Matches', ''],
    s.suggestions.map(function (it) {
      const b = it.suggestion.benchmark;
      const apply = b.suggested_rate === null ? '' :
        '!html:<button class="btn btn-primary" onclick="applySuggestion('
        + it.boq_item_id + ',' + b.suggested_rate + ',\'' 
        + encodeURIComponent(it.description) + '\')">Apply ' + b.suggested_rate + '</button>';
      return [it.line_number, it.description,
        b.suggested_rate === null ? '—' : (b.suggested_rate + ' ' + (b.currency || '')),
        b.count ? (b.min + ' – ' + b.max) : 'no match',
        b.count, apply];
    })
  );
}

async function applySuggestion(itemId, rate, encDesc) {
  await api('/api/boq-items/' + itemId + '/price', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unit_rate: rate, notes: 'historical suggestion accepted' }),
  });
  /* feedback loop: the accepted rate re-enters the corpus */
  await postJSON('/api/historical/feedback',
    { description: decodeURIComponent(encDesc), accepted_rate: rate });
  alert('Applied ' + rate + ' and recorded feedback');
  loadSuggestions();
}

document.getElementById('hist-import-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const r = await api('/api/historical/import', { method: 'POST', body: fd });
  document.getElementById('hist-import-result').textContent =
    'imported ' + r.imported + ', skipped ' + r.skipped;
});
</script>
```

- [ ] **Step 3: Create `app/templates/workbench/_deliverables.html`**

```html
<section id="tab-deliverables" class="wb-tab" data-label="Deliverables" style="display:none">
  <div class="card">
    <h3>Build submission bundle</h3>
    <label>Duration (months): <input id="deliv-months" type="number" min="0" value="0" size="6"></label>
    <label>Location: <input id="deliv-location" value="default" size="12"></label>
    <button class="btn btn-primary" onclick="buildDeliverables()">Build</button>
    <a class="btn btn-secondary" href="/api/projects/{{ project.id }}/deliverables/download">Download zip</a>
    <div id="deliv-files"></div>
  </div>
</section>
<script>
window.load_deliverables = async function () { /* built on demand */ };

async function buildDeliverables() {
  const months = document.getElementById('deliv-months').value || 0;
  const loc = document.getElementById('deliv-location').value || 'default';
  const r = await postJSON('/api/projects/' + PID + '/deliverables/build?duration_months='
    + encodeURIComponent(months) + '&location=' + encodeURIComponent(loc));
  document.getElementById('deliv-files').innerHTML =
    '<p>' + r.files.length + ' files (' + r.comparisons + ' comparisons, '
    + r.briefs + ' briefs):</p>' + tbl(['File'], r.files.map(function (f) { return [f]; }));
}
</script>
```

- [ ] **Step 4: Run tests; commit**

Run: `.venv/Scripts/python.exe -m pytest tests/ui/ -q` → PASS (8). Full suite green.

```bash
git add app/templates/workbench.html app/templates/workbench/_historical.html app/templates/workbench/_deliverables.html tests/ui/test_pages.py
git commit -m "feat(phase-6c): Historical and Deliverables workbench tabs"
```

---

## Task 6: Full-suite verification

- [ ] **Step 1:** Run `.venv/Scripts/python.exe -m pytest tests/ -q` — expected ~**267 passing** (259 + 8), zero failures.
- [ ] **Step 2:** Smoke-check route registration:
```
.venv/Scripts/python.exe -c "from app.main import app; paths=sorted({r.path for r in app.routes}); print('\n'.join(p for p in paths if 'workbench' in p or p == '/suppliers'))"
```
Expected:
```
/projects/{project_id}/workbench
/suppliers
```
- [ ] **Step 3:** Commit anything uncommitted: `git add -A && git commit -m "test(phase-6c): full suite green — workbench UI"` (skip if clean).

---

## Spec Coverage Self-Review

| plan.md NFR / capability surface | Task |
|---|---|
| UI: dashboard (already Phase 14), packages, suppliers, offers, status | 1 (suppliers), 2 (packages), 3 (offers/RFQ) |
| Human-in-the-loop: manual rate entry, suggestion accept + feedback | 2 (BOQ Set rate), 5 (Apply suggestion → PATCH + feedback) |
| Draft-only email with preview before send | 3 (Preview + explicit Send w/ confirm) |
| Template fills downloadable from the browser | 4 (BOQ + indirects multipart forms) |
| Deliverables build/download | 5 |
| No new backend surface (UI orchestrates existing tested API) | all |

**Deferred:** React SPA port (the locked D3 decision is superseded for personal use by this pragmatic Jinja workbench — revisit only if multi-user); checklist/summary UI (already exists in v1 `project.html`); browser-automation tests (smoke tests only — manual click-through is the acceptance step).
