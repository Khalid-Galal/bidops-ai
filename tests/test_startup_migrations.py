"""Startup Alembic hook: existing DBs get `upgrade head`, fresh DBs get
`stamp head`, and any failure is best-effort (never wedges startup).

alembic.command is mocked throughout -- no migration ever runs against a real
database here."""
from __future__ import annotations

import alembic.command

from app.config import get_settings
from app.main import (
    _alembic_stamp_head,
    _alembic_upgrade_head,
    _make_alembic_config,
)


def test_make_alembic_config_points_at_shipped_assets():
    cfg = _make_alembic_config()
    # alembic.ini + migrations/ are present in the repo, so a config is built.
    assert cfg is not None
    url = cfg.get_main_option("sqlalchemy.url")
    assert url == f"sqlite+aiosqlite:///{get_settings().database_path}"
    # script_location resolves to the real migrations dir (absolute).
    assert cfg.get_main_option("script_location").endswith("migrations")


def test_make_alembic_config_returns_none_when_assets_missing(monkeypatch):
    # Simulate an image that still excluded the migration assets.
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    assert _make_alembic_config() is None


def test_upgrade_head_calls_alembic_command(monkeypatch):
    calls = []
    monkeypatch.setattr(
        alembic.command, "upgrade", lambda cfg, rev: calls.append(rev)
    )
    _alembic_upgrade_head()
    assert calls == ["head"]


def test_stamp_head_calls_alembic_command(monkeypatch):
    calls = []
    monkeypatch.setattr(
        alembic.command, "stamp", lambda cfg, rev: calls.append(rev)
    )
    _alembic_stamp_head()
    assert calls == ["head"]


def test_upgrade_head_is_best_effort_on_failure(monkeypatch):
    def boom(cfg, rev):
        raise RuntimeError("migration exploded")

    monkeypatch.setattr(alembic.command, "upgrade", boom)
    # Must not propagate -- startup continues regardless.
    _alembic_upgrade_head()


def test_helpers_noop_when_config_missing(monkeypatch):
    called = []
    monkeypatch.setattr("app.main._make_alembic_config", lambda: None)
    monkeypatch.setattr(
        alembic.command, "upgrade", lambda *a, **k: called.append("upgrade")
    )
    monkeypatch.setattr(
        alembic.command, "stamp", lambda *a, **k: called.append("stamp")
    )
    _alembic_upgrade_head()
    _alembic_stamp_head()
    assert called == []
