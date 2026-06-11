"""HF Dataset snapshot persistence: archive content, restore guard, watcher,
endpoints. The hub is injected (no network), mirroring the codebase's
injectable-boundary pattern."""

from __future__ import annotations

import asyncio
import sqlite3
import tarfile
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.services.backup import backup_service as bs_module
from app.services.backup.backup_service import ARCHIVE_NAME, BackupService


class FakeHub:
    """Records create_repo/upload_file; serves a tar for hf_hub_download."""

    def __init__(self):
        self.created = []
        self.uploaded = []
        self.download_path: str | None = None

    def create_repo(self, repo_id, repo_type=None, private=None, exist_ok=None, token=None):
        self.created.append({"repo_id": repo_id, "private": private, "repo_type": repo_type})

    def upload_file(self, path_or_fileobj=None, path_in_repo=None, repo_id=None,
                    repo_type=None, token=None, commit_message=None):
        # Copy the archive aside so the test can inspect/serve it later.
        dest = Path(path_or_fileobj).with_suffix(".uploaded")
        dest.write_bytes(Path(path_or_fileobj).read_bytes())
        self.uploaded.append({"repo_id": repo_id, "path_in_repo": path_in_repo,
                              "local_copy": str(dest)})

    def hf_hub_download(self, repo_id=None, filename=None, repo_type=None, token=None):
        if self.download_path is None:
            raise FileNotFoundError("no snapshot in fake hub")
        return self.download_path


def _make_data_dir(tmp_path: Path) -> Path:
    """A realistic data dir: sqlite db + uploads + offers + regenerables."""
    data = tmp_path / "data"
    (data / "uploads" / "1").mkdir(parents=True)
    (data / "offers" / "pkg_1").mkdir(parents=True)
    (data / "packages" / "project_1").mkdir(parents=True)
    (data / "deliverables" / "project_1").mkdir(parents=True)
    db = sqlite3.connect(str(data / "bidops.db"))
    db.execute("CREATE TABLE t (x TEXT)")
    db.execute("INSERT INTO t VALUES ('hello')")
    db.commit()
    db.close()
    (data / "uploads" / "1" / "tender.pdf").write_bytes(b"%PDF-fake")
    (data / "offers" / "pkg_1" / "quote.txt").write_text("offer")
    (data / "packages" / "project_1" / "register.xlsx").write_bytes(b"regenerable")
    (data / "deliverables" / "project_1" / "summary.xlsx").write_bytes(b"regenerable")
    (data / "rules.json").write_text("{}")
    return data


def _service(tmp_path: Path, hub: FakeHub, monkeypatch) -> BackupService:
    data = tmp_path / "data"
    monkeypatch.setenv("BIDOPS_DATABASE_PATH", str(data / "bidops.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    svc = BackupService(hub=hub, data_dir=data, repo_id="user/test-data", token="tok")
    return svc


@pytest.fixture(autouse=True)
def _restore_settings_cache():
    yield
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_backup_uploads_consistent_archive_excluding_regenerables(tmp_path, monkeypatch):
    _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)

    result = await svc.backup()

    assert result["status"] == "ok"
    assert hub.created and hub.created[0]["private"] is True
    assert hub.uploaded and hub.uploaded[0]["path_in_repo"] == ARCHIVE_NAME
    with tarfile.open(hub.uploaded[0]["local_copy"], "r:gz") as tar:
        names = set(tar.getnames())
    assert "bidops.db" in names                       # consistent sqlite copy
    assert "uploads/1/tender.pdf" in names            # user uploads kept
    assert "offers/pkg_1/quote.txt" in names          # supplier files kept
    assert "rules.json" in names
    assert not any(n.startswith("packages/") for n in names)      # regenerable
    assert not any(n.startswith("deliverables/") for n in names)  # regenerable


@pytest.mark.asyncio
async def test_restore_roundtrip_into_fresh_dir(tmp_path, monkeypatch):
    _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)
    await svc.backup()
    hub.download_path = hub.uploaded[0]["local_copy"]

    # Fresh "container": empty data dir, db missing -> restore runs.
    fresh = tmp_path / "fresh"
    monkeypatch.setenv("BIDOPS_DATABASE_PATH", str(fresh / "bidops.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    svc2 = BackupService(hub=hub, data_dir=fresh, repo_id="user/test-data", token="tok")

    assert svc2.restore_sync() is True
    restored_db = sqlite3.connect(str(fresh / "bidops.db"))
    rows = restored_db.execute("SELECT x FROM t").fetchall()
    restored_db.close()
    assert rows == [("hello",)]
    assert (fresh / "uploads" / "1" / "tender.pdf").read_bytes() == b"%PDF-fake"


@pytest.mark.asyncio
async def test_restore_never_clobbers_existing_db(tmp_path, monkeypatch):
    data = _make_data_dir(tmp_path)
    hub = FakeHub()
    hub.download_path = "should-not-be-used"
    svc = _service(tmp_path, hub, monkeypatch)

    assert svc.restore_sync() is False  # db exists -> guarded
    db = sqlite3.connect(str(data / "bidops.db"))
    assert db.execute("SELECT x FROM t").fetchall() == [("hello",)]
    db.close()


def test_restore_missing_snapshot_starts_fresh(tmp_path, monkeypatch):
    hub = FakeHub()  # download raises FileNotFoundError
    monkeypatch.setenv("BIDOPS_DATABASE_PATH", str(tmp_path / "data" / "bidops.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    svc = BackupService(hub=hub, data_dir=tmp_path / "data",
                        repo_id="user/test-data", token="tok")
    assert svc.restore_sync() is False  # logged + fresh start, no raise


def test_disabled_without_repo_or_token(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    svc = BackupService(hub=FakeHub(), data_dir=tmp_path, repo_id="", token="")
    assert svc.enabled() is False


@pytest.mark.asyncio
async def test_disabled_backup_is_noop(tmp_path):
    hub = FakeHub()
    svc = BackupService(hub=hub, data_dir=tmp_path, repo_id="", token="")
    assert (await svc.backup())["status"] == "disabled"
    assert not hub.uploaded


@pytest.mark.asyncio
async def test_dirty_tracks_changes_since_last_backup(tmp_path, monkeypatch):
    data = _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)

    assert svc.dirty() is True            # never backed up
    await svc.backup()
    assert svc.dirty() is False           # clean right after snapshot
    time.sleep(0.05)
    f = data / "uploads" / "1" / "new.pdf"
    f.write_bytes(b"%PDF-2")
    now = time.time()
    import os

    os.utime(f, (now + 5, now + 5))       # ensure mtime strictly newer
    assert svc.dirty() is True            # change detected


@pytest.mark.asyncio
async def test_backup_endpoints(tmp_path, monkeypatch):
    _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)
    monkeypatch.setattr(bs_module, "_service", svc)

    from app.api.backup import router

    api = FastAPI()
    api.include_router(router, prefix="/api")
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        status = (await c.get("/api/backup/status")).json()
        assert status["enabled"] is True
        assert status["repo"] == "user/test-data"
        assert status["last_backup_at"] is None

        r = await c.post("/api/backup")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        status = (await c.get("/api/backup/status")).json()
        assert status["last_backup_at"] is not None
        assert status["last_error"] is None


@pytest.mark.asyncio
async def test_backup_endpoint_503_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    svc = BackupService(hub=FakeHub(), data_dir=tmp_path, repo_id="", token="")
    monkeypatch.setattr(bs_module, "_service", svc)

    from app.api.backup import router

    api = FastAPI()
    api.include_router(router, prefix="/api")
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.post("/api/backup")).status_code == 503


def test_backup_settings_defaults():
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.backup_dataset_repo == ""
    assert s.backup_interval_seconds == 60


@pytest.mark.asyncio
async def test_deleting_a_file_marks_dirty(tmp_path, monkeypatch):
    """Deletions bump no mtime -- the file-set diff must catch them, else a
    later restore resurrects deleted files (review HIGH finding)."""
    data = _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)

    await svc.backup()
    assert svc.dirty() is False
    (data / "uploads" / "1" / "tender.pdf").unlink()
    assert svc.dirty() is True            # deletion detected via file-set diff

    await svc.backup()
    assert svc.dirty() is False           # new snapshot reflects the deletion
    with tarfile.open(hub.uploaded[-1]["local_copy"], "r:gz") as tar:
        assert "uploads/1/tender.pdf" not in set(tar.getnames())


@pytest.mark.asyncio
async def test_manual_backup_endpoint_cooldown_429(tmp_path, monkeypatch):
    """Unauthenticated POST /api/backup must not allow upload spam."""
    _make_data_dir(tmp_path)
    hub = FakeHub()
    svc = _service(tmp_path, hub, monkeypatch)
    monkeypatch.setattr(bs_module, "_service", svc)

    from app.api.backup import router

    api = FastAPI()
    api.include_router(router, prefix="/api")
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.post("/api/backup")).status_code == 200
        r = await c.post("/api/backup")   # immediate retry -> cooldown
        assert r.status_code == 429
    assert len(hub.uploaded) == 1


def test_restore_rejects_corrupt_archive_and_leaves_dir_clean(tmp_path, monkeypatch):
    """A truncated/garbage snapshot must not leave partial files in data/."""
    hub = FakeHub()
    garbage = tmp_path / "bad.tar.gz"
    garbage.write_bytes(b"not a tarball at all")
    hub.download_path = str(garbage)
    fresh = tmp_path / "fresh"
    monkeypatch.setenv("BIDOPS_DATABASE_PATH", str(fresh / "bidops.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    svc = BackupService(hub=hub, data_dir=fresh, repo_id="user/test-data", token="tok")

    assert svc.restore_sync() is False
    assert not (fresh / "bidops.db").exists()          # no partial restore
    assert not (fresh.parent / "fresh.restore_tmp").exists()  # staging cleaned
