# Phase 6B — Configurable Rules / Market System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a fully user-configurable, market-neutral business-rules system (scoring weights, packaging rules, commercial/markup/VAT, measurement units, compliance triggers, indirects rates, email/naming conventions) loaded from JSON with typed validation and a GET/PUT API.

**Architecture:** Neutral defaults ship in a committed `config/rules.default.json`. A `RulesService` loads the defaults, deep-merges an optional user-override file (`data/rules.json`, gitignored, written by PUT), and returns a validated `RulesConfig` Pydantic model. A small API (`GET/PUT /api/rules`) reads and persists the effective config so the Phase 6C settings UI can edit it. No market specifics are hardcoded (currency/VAT/markups/location factors are all data). LLM settings stay in `app/config.py` (single source of truth) and are intentionally NOT duplicated here.

**Tech Stack:** Python 3.11, Pydantic v2, FastAPI, httpx (ASGITransport for API tests), pytest.

**Decomposition note:** Plan **6B** of Phase 6 (after 6A data models, merged). Sibling: **6C** React SPA shell. Downstream phases (8 packaging, 9 pricing, 10 offers, 12 indirects) will *consume* this config; 6B only builds the config infrastructure.

---

## File Structure

- `config/rules.default.json` — CREATE: committed market-neutral default rules.
- `app/schemas/rules.py` — CREATE: typed `RulesConfig` + nested section models.
- `app/services/rules/__init__.py` — CREATE: exports `RulesService`, `get_rules_service`.
- `app/services/rules/rules_service.py` — CREATE: load (defaults + user overlay), deep-merge, save.
- `app/api/rules.py` — CREATE: `GET /api/rules`, `PUT /api/rules`.
- `app/main.py` — MODIFY: register the rules router.
- `tests/services/__init__.py`, `tests/services/test_rules_service.py` — CREATE.
- `tests/api/__init__.py`, `tests/api/test_rules_api.py` — CREATE.
- `.gitignore` — MODIFY: ignore `data/rules.json` (user overrides; already covered by `data/`, verify).

---

## Task 1: Market-neutral default rules JSON

**Files:**
- Create: `config/rules.default.json`

- [ ] **Step 1: Create `config/rules.default.json`**

```json
{
  "scoring": {
    "weights": {
      "technical_compliance": 0.30,
      "price": 0.35,
      "delivery_time": 0.15,
      "payment_terms": 0.10,
      "supplier_rating": 0.10
    },
    "thresholds": { "excellent": 90, "good": 75, "acceptable": 60, "poor": 40 }
  },
  "keywords": {
    "mandatory": ["must", "shall", "required", "mandatory", "يجب", "إلزامي"],
    "deadline": ["deadline", "due date", "submission", "closing date", "موعد التسليم"],
    "bond": ["tender bond", "bid bond", "bank guarantee", "performance bond", "ضمان العطاء"],
    "payment": ["advance payment", "retention", "milestone", "interim payment", "دفعة مقدمة"]
  },
  "packaging": {
    "min_items_per_package": 5,
    "max_items_per_package": 100,
    "grouping_criteria": ["trade_category", "spec_section"],
    "trade_categories": {
      "concrete": ["concrete", "formwork", "rebar", "reinforcement"],
      "structural_steel": ["steel", "fabrication", "erection"],
      "mep": ["mechanical", "electrical", "plumbing", "hvac", "fire fighting"],
      "finishes": ["flooring", "painting", "ceiling", "partition", "cladding"],
      "civil": ["excavation", "earthwork", "roads", "utilities"]
    }
  },
  "email": {
    "provider": "smtp",
    "draft_only": true,
    "from_address": "",
    "reply_to": "",
    "default_language": "en",
    "attachment_size_limit_mb": 25,
    "subject_formats": {
      "rfq": "[{project_code}] RFQ - {package_name}",
      "clarification": "[{project_code}] Clarification Request - {supplier_name}",
      "reminder": "[{project_code}] Reminder - {package_name}"
    }
  },
  "naming": {
    "project_code_format": "PRJ-{year}-{seq:04d}",
    "package_code_format": "PKG-{project_code}-{trade_abbr}-{seq:03d}",
    "offer_folder_format": "{package_code}/{supplier_name}",
    "document_naming": "{project_code}_{category}_{date}_{seq}",
    "trade_abbreviations": {
      "concrete": "CON", "structural_steel": "STL", "mep": "MEP",
      "electrical": "ELE", "mechanical": "MEC", "plumbing": "PLB",
      "hvac": "HVAC", "finishes": "FIN", "civil": "CIV"
    }
  },
  "commercial": {
    "currency": "USD",
    "vat_rate": 0.0,
    "default_validity_days": 90,
    "default_payment_terms": "Net 30",
    "markup": { "profit": 0.10, "overhead": 0.08, "contingency": 0.05, "risk": 0.03 }
  },
  "measurement": {
    "contract_type": "lumpsum",
    "quantity_tolerance": 0.05,
    "unit_mappings": {
      "sqm": "m2", "sq.m": "m2", "square meter": "m2",
      "lm": "m", "lin.m": "m", "linear meter": "m",
      "cum": "m3", "cu.m": "m3", "cubic meter": "m3",
      "nr": "no", "nos": "no", "number": "no", "ea": "no", "each": "no",
      "ls": "ls", "lump sum": "ls"
    }
  },
  "compliance": {
    "required_offer_fields": ["total_price", "validity_period", "delivery_time"],
    "non_compliance_triggers": ["exclusion", "deviation", "exception", "not included", "غير مشمول", "استثناء"]
  },
  "indirects": {
    "percentage_based": {
      "site_supervision": 0.03, "quality_control": 0.01, "safety": 0.015,
      "insurance": 0.01, "temporary_works": 0.02
    },
    "duration_based": {
      "project_manager": { "monthly_rate": 0.0 },
      "site_engineer": { "monthly_rate": 0.0 },
      "safety_officer": { "monthly_rate": 0.0 }
    },
    "location_factors": { "default": 1.0, "remote": 1.15 }
  }
}
```

- [ ] **Step 2: Verify it is valid JSON**

Run: `.venv/Scripts/python.exe -c "import json,pathlib; json.loads(pathlib.Path('config/rules.default.json').read_text(encoding='utf-8')); print('valid json')"`
Expected: `valid json`

- [ ] **Step 3: Commit**

```bash
git add config/rules.default.json
git commit -m "feat(rules): add market-neutral default rules.json"
```

---

## Task 2: Typed `RulesConfig` Pydantic schema

**Files:**
- Create: `app/schemas/rules.py`
- Test: `tests/services/__init__.py` (empty), `tests/services/test_rules_schema.py`

- [ ] **Step 1: Write the failing test `tests/services/test_rules_schema.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_rules_schema.py -v`
Expected: FAIL (ModuleNotFoundError: app.schemas.rules). (Create `tests/services/__init__.py` empty first so the package imports.)

- [ ] **Step 3: Create `app/schemas/rules.py`**

```python
"""Typed Pydantic models for the configurable business-rules system.

Mirrors config/rules.default.json. Every section has defaults so RulesConfig()
constructs a complete, valid config without any file present.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    technical_compliance: float = 0.30
    price: float = 0.35
    delivery_time: float = 0.15
    payment_terms: float = 0.10
    supplier_rating: float = 0.10


class ScoringThresholds(BaseModel):
    excellent: float = 90
    good: float = 75
    acceptable: float = 60
    poor: float = 40


class Scoring(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)


class Keywords(BaseModel):
    mandatory: list[str] = Field(default_factory=list)
    deadline: list[str] = Field(default_factory=list)
    bond: list[str] = Field(default_factory=list)
    payment: list[str] = Field(default_factory=list)


class Packaging(BaseModel):
    min_items_per_package: int = 5
    max_items_per_package: int = 100
    grouping_criteria: list[str] = Field(
        default_factory=lambda: ["trade_category", "spec_section"]
    )
    trade_categories: dict[str, list[str]] = Field(default_factory=dict)


class EmailSubjectFormats(BaseModel):
    rfq: str = "[{project_code}] RFQ - {package_name}"
    clarification: str = "[{project_code}] Clarification Request - {supplier_name}"
    reminder: str = "[{project_code}] Reminder - {package_name}"


class EmailRules(BaseModel):
    provider: str = "smtp"
    draft_only: bool = True
    from_address: str = ""
    reply_to: str = ""
    default_language: str = "en"
    attachment_size_limit_mb: int = 25
    subject_formats: EmailSubjectFormats = Field(default_factory=EmailSubjectFormats)


class Naming(BaseModel):
    project_code_format: str = "PRJ-{year}-{seq:04d}"
    package_code_format: str = "PKG-{project_code}-{trade_abbr}-{seq:03d}"
    offer_folder_format: str = "{package_code}/{supplier_name}"
    document_naming: str = "{project_code}_{category}_{date}_{seq}"
    trade_abbreviations: dict[str, str] = Field(default_factory=dict)


class Markup(BaseModel):
    profit: float = 0.10
    overhead: float = 0.08
    contingency: float = 0.05
    risk: float = 0.03


class Commercial(BaseModel):
    currency: str = "USD"
    vat_rate: float = 0.0
    default_validity_days: int = 90
    default_payment_terms: str = "Net 30"
    markup: Markup = Field(default_factory=Markup)


class Measurement(BaseModel):
    contract_type: str = "lumpsum"
    quantity_tolerance: float = 0.05
    unit_mappings: dict[str, str] = Field(default_factory=dict)


class Compliance(BaseModel):
    required_offer_fields: list[str] = Field(
        default_factory=lambda: ["total_price", "validity_period", "delivery_time"]
    )
    non_compliance_triggers: list[str] = Field(default_factory=list)


class DurationBasedRole(BaseModel):
    monthly_rate: float = 0.0


class Indirects(BaseModel):
    percentage_based: dict[str, float] = Field(default_factory=dict)
    duration_based: dict[str, DurationBasedRole] = Field(default_factory=dict)
    location_factors: dict[str, float] = Field(
        default_factory=lambda: {"default": 1.0, "remote": 1.15}
    )


class RulesConfig(BaseModel):
    """Complete business-rules configuration. All sections default-constructible."""

    scoring: Scoring = Field(default_factory=Scoring)
    keywords: Keywords = Field(default_factory=Keywords)
    packaging: Packaging = Field(default_factory=Packaging)
    email: EmailRules = Field(default_factory=EmailRules)
    naming: Naming = Field(default_factory=Naming)
    commercial: Commercial = Field(default_factory=Commercial)
    measurement: Measurement = Field(default_factory=Measurement)
    compliance: Compliance = Field(default_factory=Compliance)
    indirects: Indirects = Field(default_factory=Indirects)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_rules_schema.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/rules.py tests/services/__init__.py tests/services/test_rules_schema.py
git commit -m "feat(rules): typed RulesConfig Pydantic schema"
```

---

## Task 3: `RulesService` loader (defaults + user overlay + save)

**Files:**
- Create: `app/services/rules/__init__.py`, `app/services/rules/rules_service.py`
- Test: `tests/services/test_rules_service.py`

- [ ] **Step 1: Write the failing test `tests/services/test_rules_service.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_rules_service.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create `app/services/rules/rules_service.py`**

```python
"""Loads, merges, and persists the business-rules configuration.

Effective config = committed defaults (config/rules.default.json) deep-merged
with an optional user-override file (data/rules.json, written via the API).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.rules import RulesConfig

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULTS_PATH = _REPO_ROOT / "config" / "rules.default.json"
_USER_PATH = _REPO_ROOT / "data" / "rules.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins on leaves)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class RulesService:
    """Service for reading and persisting the effective rules configuration."""

    def __init__(
        self,
        defaults_path: Path | None = None,
        user_path: Path | None = None,
    ) -> None:
        self._defaults_path = defaults_path or _DEFAULTS_PATH
        self._user_path = user_path or _USER_PATH

    def load(self) -> RulesConfig:
        """Return the effective config: defaults deep-merged with user overrides."""
        data = json.loads(self._defaults_path.read_text(encoding="utf-8"))
        if self._user_path.exists():
            user = json.loads(self._user_path.read_text(encoding="utf-8"))
            data = _deep_merge(data, user)
        return RulesConfig.model_validate(data)

    def save(self, config: RulesConfig) -> None:
        """Persist the full effective config to the user-override file."""
        self._user_path.parent.mkdir(parents=True, exist_ok=True)
        self._user_path.write_text(
            config.model_dump_json(indent=2), encoding="utf-8"
        )
```

- [ ] **Step 4: Create `app/services/rules/__init__.py`**

```python
"""Rules configuration service package."""

from functools import lru_cache

from app.services.rules.rules_service import RulesService


@lru_cache
def get_rules_service() -> RulesService:
    """Cached default RulesService (defaults + data/rules.json)."""
    return RulesService()


__all__ = ["RulesService", "get_rules_service"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/services/test_rules_service.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/services/rules/ tests/services/test_rules_service.py
git commit -m "feat(rules): RulesService loader with defaults + user-override deep-merge"
```

---

## Task 4: Rules API (`GET`/`PUT /api/rules`)

**Files:**
- Create: `app/api/rules.py`
- Modify: `app/main.py` (register router)
- Test: `tests/api/__init__.py` (empty), `tests/api/test_rules_api.py`

- [ ] **Step 1: Write the failing test `tests/api/test_rules_api.py`**

```python
import httpx
import pytest


@pytest.fixture
def rules_client(tmp_path, monkeypatch):
    """ASGI client with the rules service pointed at a temp user-override file."""
    import app.api.rules as rules_api
    from app.services.rules.rules_service import RulesService

    svc = RulesService(user_path=tmp_path / "rules.json")
    monkeypatch.setattr(rules_api, "_rules_service", svc, raising=False)
    monkeypatch.setattr(rules_api, "get_rules_service", lambda: svc)

    from app.main import app
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_get_rules_returns_defaults(rules_client):
    async with rules_client as client:
        r = await client.get("/api/rules")
    assert r.status_code == 200
    body = r.json()
    assert body["commercial"]["currency"] == "USD"
    assert body["email"]["draft_only"] is True


async def test_put_rules_persists_and_get_reflects(rules_client):
    async with rules_client as client:
        current = (await client.get("/api/rules")).json()
        current["commercial"]["currency"] = "EGP"
        current["commercial"]["vat_rate"] = 0.14
        put = await client.put("/api/rules", json=current)
        assert put.status_code == 200
        after = (await client.get("/api/rules")).json()
    assert after["commercial"]["currency"] == "EGP"
    assert after["commercial"]["vat_rate"] == 0.14
    assert after["measurement"]["unit_mappings"]["sqm"] == "m2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/api/test_rules_api.py -v`
Expected: FAIL (ModuleNotFoundError: app.api.rules). (Create `tests/api/__init__.py` empty first.)

- [ ] **Step 3: Create `app/api/rules.py`**

```python
"""Rules configuration API: read and update the effective business rules."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.rules import RulesConfig
from app.services.rules import get_rules_service

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=RulesConfig)
async def read_rules() -> RulesConfig:
    """Return the effective rules config (defaults merged with user overrides)."""
    return get_rules_service().load()


@router.put("", response_model=RulesConfig)
async def update_rules(config: RulesConfig) -> RulesConfig:
    """Persist a new full rules config and return the stored result."""
    service = get_rules_service()
    service.save(config)
    return service.load()
```

- [ ] **Step 4: Register the router in `app/main.py`**

Add an import alongside the other router imports:

```python
from app.api.rules import router as rules_router
```

Add registration alongside the other `app.include_router(..., prefix="/api")` lines:

```python
app.include_router(rules_router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/api/test_rules_api.py -v`
Expected: PASS (2 passed).

Note: the test monkeypatches `app.api.rules.get_rules_service` to a temp-file-backed service so the suite never writes the real `data/rules.json`.

- [ ] **Step 6: Commit**

```bash
git add app/api/rules.py app/main.py tests/api/__init__.py tests/api/test_rules_api.py
git commit -m "feat(rules): GET/PUT /api/rules endpoints"
```

---

## Task 5: Full-suite check + gitignore user overrides

**Files:**
- Modify: `.gitignore` (verify `data/` already ignores `data/rules.json`)

- [ ] **Step 1: Confirm user overrides are gitignored**

Run: `git check-ignore data/rules.json`
Expected: prints `data/rules.json` (already covered by the `data/` rule). If NOT ignored, add `data/rules.json` to `.gitignore`.

- [ ] **Step 2: Run the FULL test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS (Phase 6A model tests + 6B schema/service/api tests). Report the count.

- [ ] **Step 3: Boot smoke — confirm the app imports with the new router**

Run: `.venv/Scripts/python.exe -c "import app.main; print('routes:', [r.path for r in app.main.app.routes if getattr(r,'path','').endswith('/rules')])"`
Expected: shows `/api/rules`.

- [ ] **Step 4: Commit (if .gitignore changed)**

```bash
git add .gitignore
git commit -m "chore: ensure data/rules.json (user rule overrides) is gitignored"
```

---

## Self-Review (completed by author)

- **Spec coverage:** Implements the "configurable rules/market system (rules.json + RulesConfig loader, fully market-configurable, settings UI editable)" deliverable of Phase 6. Currency/VAT/markups/location-factors/scoring/packaging/email/measurement/compliance/indirects all data-driven; defaults are market-neutral (USD, 0% VAT, generic location factors). GET/PUT API enables the 6C settings UI.
- **Out of scope (correct):** LLM routing (owned by `app/config.py`), and *consumption* of these rules by packaging/pricing/offer/indirects services (their own phases).
- **Placeholder scan:** All code is complete and inline (no TODOs). Default JSON, schema, service, API, and tests are fully specified.
- **Type consistency:** `RulesConfig` shape matches `config/rules.default.json` key-for-key. `RulesService(user_path=...)`/`load()`/`save()` signatures consistent across service and API and tests. API monkeypatch target (`app.api.rules.get_rules_service`) matches the import in `app/api/rules.py`.
- **Test isolation:** service tests use `tmp_path`; API test monkeypatches the service to a temp file so the real `data/rules.json` is never written by the suite.
