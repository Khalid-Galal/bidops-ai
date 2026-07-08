"""Snapshot-based persistence to a private Hugging Face Dataset repo.

Free-tier alternative to a persistent disk: the whole runtime state directory
(``data/`` -- SQLite DB, uploaded files, offer files, Chroma index, rules
override) is tar'd and pushed to a private HF Dataset repo, and restored from
there on a fresh boot. Survives Space rebuilds, restarts, and sleep.

Design notes:
- ``huggingface_hub`` is an existing dependency (docling pulls it); the hub
  module is INJECTABLE for tests, mirroring the DocumentLinker/SMTPSender
  pattern used across the codebase.
- The SQLite file is copied via the sqlite3 backup API before archiving so the
  snapshot is consistent even while the app is live; ``-wal``/``-shm``/journal
  side files are skipped (the backup copy is self-contained).
- ``packages/`` and ``deliverables/`` are EXCLUDED: they are regenerable
  artifacts (re-run export/build); excluding them keeps snapshots small.
- Restore only runs when the database file does not exist yet (fresh
  container). It never clobbers live local data or a persistent-disk volume.
- All tar/network work runs in a thread (``asyncio.to_thread``) -- never on
  the event loop (Phase 15 lesson).

Rollback / dataset growth:
- Every successful ``backup()`` overwrites ``ARCHIVE_NAME`` at the head of the
  dataset repo's default branch, but the HF Dataset repo is git-backed, so
  each snapshot is also a distinct commit ("revision"). ``restore_sync`` and
  ``restore()`` accept an optional ``revision`` (a commit SHA, as returned by
  ``list_revisions()``/``GET /backup/revisions``) to roll back to an older
  snapshot instead of the latest one.
- To bound the repo's history growth, every ``SQUASH_EVERY_N_BACKUPS``
  successful backups the service squashes the whole commit history into one
  commit via ``huggingface_hub``'s ``super_squash_history`` (the minimal
  retention primitive the Hub API offers). This is irreversible and discards
  older revisions -- rollback only reaches back to snapshots taken since the
  last squash. ``POST /api/backup/restore`` (optionally with
  ``?revision=<sha>``) exposes manual rollback; ``GET /api/backup/revisions``
  lists the revisions currently restorable.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sqlite3
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

ARCHIVE_NAME = "bidops-data.tar.gz"

# Hard ceilings so a hung HF Hub call can never wedge startup or the backup
# lock forever (the orphaned worker thread finishes/dies on its own).
ARCHIVE_TIMEOUT_S = 300
UPLOAD_TIMEOUT_S = 600
RESTORE_TIMEOUT_S = 180
SQUASH_TIMEOUT_S = 60

# Retention: bound the dataset repo's git history growth by squashing it back
# to a single commit every N successful backups. Squashing is irreversible
# (huggingface_hub's ``super_squash_history``) so rollback via ``revision``
# only reaches snapshots taken since the last squash -- an accepted tradeoff
# for a single-user tool where unbounded history growth is the bigger risk.
SQUASH_EVERY_N_BACKUPS = 20

# Top-level entries under data/ that are regenerable artifacts -- not worth
# snapshot space. Everything else (db, uploads, offers, chroma, rules.json)
# is state that cannot be rebuilt and IS included.
EXCLUDED_TOPLEVEL = {"packages", "deliverables"}

# SQLite side files: never archived raw (the consistent backup copy replaces
# the main file; side files would be stale/corrupt on restore).
_DB_SIDE_SUFFIXES = ("-wal", "-shm", "-journal")


class BackupService:
    """Debounced snapshots of the data dir to a HF dataset repo."""

    def __init__(
        self,
        hub=None,
        data_dir: str | Path = "data",
        repo_id: str | None = None,
        token: str | None = None,
    ) -> None:
        self._hub = hub
        self._data_dir = Path(data_dir)
        self._repo_id = repo_id
        self._token = token
        self._lock = asyncio.Lock()
        self._repo_ready = False
        self.last_backup_at: float = 0.0  # wall-clock of last successful backup
        self.last_error: str | None = None
        # Names archived by the last successful snapshot: lets dirty() detect
        # DELETIONS (a removed file bumps no mtime but changes the file set).
        self._last_archive_names: frozenset[str] | None = None
        self._consecutive_failures = 0
        # Backups since the last history squash; bounds dataset repo growth.
        self._backups_since_squash = 0

    # -- configuration -----------------------------------------------------

    @property
    def repo_id(self) -> str:
        if self._repo_id is not None:
            return self._repo_id
        return get_settings().backup_dataset_repo

    @property
    def token(self) -> str:
        if self._token is not None:
            return self._token
        settings = get_settings()
        if settings.hf_token:
            return settings.hf_token
        import os

        return os.environ.get("HF_TOKEN", "")

    def enabled(self) -> bool:
        """Backups are on when both a target repo and a token are configured."""
        return bool(self.repo_id and self.token)

    def _get_hub(self):
        if self._hub is None:
            import huggingface_hub

            self._hub = huggingface_hub
        return self._hub

    # -- snapshot building (sync; run in a thread) ---------------------------

    def _db_paths(self) -> tuple[Path, str]:
        """Absolute DB path + its archive name relative to the data dir."""
        db_path = Path(get_settings().database_path)
        try:
            rel = db_path.relative_to(self._data_dir)
            return db_path, str(rel.as_posix())
        except ValueError:
            # DB configured outside the data dir -- archive it at the root.
            return db_path, db_path.name

    def _iter_snapshot_files(self):
        """Yield (absolute_path, arcname) for every file to archive."""
        db_path, _ = self._db_paths()
        skip_paths = {db_path} | {
            db_path.with_name(db_path.name + suffix) for suffix in _DB_SIDE_SUFFIXES
        }
        if not self._data_dir.is_dir():
            return
        try:
            data_root = self._data_dir.resolve()
        except OSError:  # pragma: no cover - defensive
            return
        for entry in sorted(self._data_dir.iterdir()):
            if entry.name in EXCLUDED_TOPLEVEL:
                continue
            if entry.is_file():
                if entry in skip_paths:
                    continue
                yield entry, entry.name
            elif entry.is_dir():
                for f in sorted(entry.rglob("*")):
                    # Skip the live DB wherever it is configured, and anything
                    # a symlink points outside the data dir (containment).
                    if not f.is_file() or f in skip_paths:
                        continue
                    try:
                        if not f.resolve().is_relative_to(data_root):
                            logger.warning("Skipping %s: outside data dir", f)
                            continue
                        arcname = f.relative_to(self._data_dir).as_posix()
                    except (OSError, ValueError):
                        logger.warning("Skipping unarchivable path: %s", f)
                        continue
                    yield f, arcname

    def _build_archive(self, out_path: Path) -> tuple[int, frozenset[str]]:
        """Write the snapshot tarball; returns (file count, archived names)."""
        db_path, db_arcname = self._db_paths()
        names: set[str] = set()
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(out_path, "w:gz") as tar:
                # Consistent SQLite copy via the backup API (safe while live).
                if db_path.exists():
                    db_copy = Path(tmp) / "db_snapshot.sqlite"
                    src = sqlite3.connect(str(db_path))
                    try:
                        dst = sqlite3.connect(str(db_copy))
                        try:
                            src.backup(dst)
                        finally:
                            dst.close()
                    finally:
                        src.close()
                    tar.add(str(db_copy), arcname=db_arcname)
                    names.add(db_arcname)
                for path, arcname in self._iter_snapshot_files():
                    # A file can vanish or be mid-write between iteration and
                    # tar.add (live uploads): skip it rather than aborting the
                    # whole snapshot; the watcher catches it next cycle.
                    try:
                        tar.add(str(path), arcname=arcname)
                        names.add(arcname)
                    except (OSError, tarfile.TarError) as exc:
                        logger.warning("Snapshot skipped %s: %s", path, exc)
        return len(names), frozenset(names)

    def _upload_archive(self, archive: Path) -> None:
        hub = self._get_hub()
        if not self._repo_ready:
            hub.create_repo(
                self.repo_id,
                repo_type="dataset",
                private=True,
                exist_ok=True,
                token=self.token,
            )
            self._repo_ready = True
        hub.upload_file(
            path_or_fileobj=str(archive),
            path_in_repo=ARCHIVE_NAME,
            repo_id=self.repo_id,
            repo_type="dataset",
            token=self.token,
            commit_message=f"snapshot {datetime.now(timezone.utc).isoformat()}",
        )

    def _squash_history(self) -> None:
        """Collapse the dataset repo's commit history to bound its growth."""
        hub = self._get_hub()
        hub.super_squash_history(repo_id=self.repo_id, repo_type="dataset", token=self.token)

    def list_revisions(self) -> list[dict]:
        """Commits on the dataset repo's default branch, newest first.

        Each entry's ``commit_id`` is a valid ``revision`` for ``restore()``/
        ``restore_sync()``. Returns an empty list on any failure (repo not
        created yet, network, disabled).
        """
        if not self.enabled():
            return []
        hub = self._get_hub()
        try:
            commits = hub.list_repo_commits(
                repo_id=self.repo_id, repo_type="dataset", token=self.token
            )
        except Exception as exc:
            logger.info("Could not list backup revisions: %s", exc)
            return []
        return [
            {
                "commit_id": c.commit_id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in commits
        ]

    # -- public API ----------------------------------------------------------

    def backup_in_progress(self) -> bool:
        return self._lock.locked()

    async def backup(self) -> dict:
        """Snapshot + upload now. Serialized; safe to call concurrently."""
        if not self.enabled():
            return {"status": "disabled"}
        async with self._lock:
            started = time.time()
            tmp_file = Path(tempfile.gettempdir()) / f"bidops_snapshot_{int(started)}.tar.gz"
            try:
                count, names = await asyncio.wait_for(
                    asyncio.to_thread(self._build_archive, tmp_file),
                    timeout=ARCHIVE_TIMEOUT_S,
                )
                await asyncio.wait_for(
                    asyncio.to_thread(self._upload_archive, tmp_file),
                    timeout=UPLOAD_TIMEOUT_S,
                )
                # Stamp with the time the snapshot STARTED: changes made while
                # archiving stay "newer than last backup" for the watcher.
                self.last_backup_at = started
                self._last_archive_names = names
                self.last_error = None
                self._consecutive_failures = 0
                size = tmp_file.stat().st_size
                logger.info(
                    "Backup uploaded to %s: %d files, %d bytes", self.repo_id, count, size
                )
                # Retention: squash history periodically to bound repo growth.
                # Best-effort -- a failed squash must not fail the backup that
                # already succeeded.
                self._backups_since_squash += 1
                if self._backups_since_squash >= SQUASH_EVERY_N_BACKUPS:
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(self._squash_history), timeout=SQUASH_TIMEOUT_S
                        )
                        self._backups_since_squash = 0
                    except Exception as exc:
                        logger.warning("Backup history squash failed: %s", exc)
                return {"status": "ok", "files": count, "bytes": size}
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self._consecutive_failures += 1
                # Escalate persistent failures so they surface in log review:
                # a permanently-broken backup is a silent data-loss risk.
                log = logger.error if self._consecutive_failures >= 3 else logger.warning
                log(
                    "Backup failed (%d consecutive): %s",
                    self._consecutive_failures,
                    self.last_error,
                )
                return {"status": "error", "error": self.last_error}
            finally:
                tmp_file.unlink(missing_ok=True)

    def restore_sync(self, revision: str | None = None, force: bool = False) -> bool:
        """Restore a snapshot into the data dir (fresh boot only by default).

        ``revision`` is an optional dataset repo commit SHA (see
        ``list_revisions()``) to roll back to an older snapshot instead of
        the latest one on the default branch.

        ``force=True`` is the explicit rollback path: it skips the "DB
        already exists" fresh-boot guard and overwrites existing local
        entries with the snapshot's, instead of skipping them. Only the
        manual restore API/CLI entrypoint should ever pass ``force=True`` --
        the startup auto-restore must keep the guard.

        Returns True when a snapshot was restored. Never raises: any failure
        (no repo yet, no snapshot yet, network) logs and starts fresh.
        """
        if not self.enabled():
            return False
        db_path, _ = self._db_paths()
        if db_path.exists() and not force:
            logger.info("Restore skipped: %s already exists (live data)", db_path)
            return False
        # Extract into a STAGING dir, integrity-check the DB, then move into
        # place -- a container killed mid-extract must never leave a partial
        # (or corrupt) data dir that the db-exists guard would then protect.
        staging = self._data_dir.parent / (self._data_dir.name + ".restore_tmp")
        try:
            hub = self._get_hub()
            archive = hub.hf_hub_download(
                repo_id=self.repo_id,
                filename=ARCHIVE_NAME,
                repo_type="dataset",
                revision=revision,
                token=self.token,
            )
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True)
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(path=str(staging), filter="data")
            _, db_arcname = self._db_paths()
            staged_db = staging / db_arcname
            if staged_db.exists():
                conn = sqlite3.connect(str(staged_db))
                try:
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                finally:
                    conn.close()
                if not result or result[0] != "ok":
                    raise RuntimeError(f"snapshot DB failed integrity_check: {result}")
            self._data_dir.mkdir(parents=True, exist_ok=True)
            for entry in staging.iterdir():
                target = self._data_dir / entry.name
                if target.exists():
                    if not force:
                        logger.warning("Restore: %s already exists, keeping local copy", target)
                        continue
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(entry), str(target))
            logger.info(
                "Restored snapshot from %s (revision=%s) into %s",
                self.repo_id,
                revision or "latest",
                self._data_dir,
            )
            return True
        except Exception as exc:
            logger.info(
                "No snapshot restored (%s: %s) -- starting fresh", type(exc).__name__, exc
            )
            return False
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    async def restore(self, revision: str | None = None, force: bool = False) -> dict:
        """Async wrapper around ``restore_sync`` for the manual restore API.

        Shares ``backup()``'s lock so a restore and a snapshot can never run
        concurrently against the same data dir.
        """
        if not self.enabled():
            return {"status": "disabled"}
        async with self._lock:
            try:
                restored = await asyncio.wait_for(
                    asyncio.to_thread(self.restore_sync, revision, force),
                    timeout=RESTORE_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                return {"status": "error", "error": "restore timed out"}
            if restored:
                return {"status": "ok", "revision": revision or "latest"}
            return {"status": "error", "error": "no snapshot restored (see logs)"}

    # -- change watcher --------------------------------------------------------

    def _scan(self) -> tuple[float, frozenset[str]]:
        """Newest mtime + current file-name set across snapshot-relevant files."""
        latest = 0.0
        names: set[str] = set()
        db_path, db_arcname = self._db_paths()
        if db_path.exists():
            latest = db_path.stat().st_mtime
            names.add(db_arcname)
        for path, arcname in self._iter_snapshot_files():
            names.add(arcname)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest:
                latest = mtime
        return latest, frozenset(names)

    def dirty(self) -> bool:
        """True when data changed after the last successful backup.

        Two signals: any file newer than the last snapshot, OR the file SET
        differing from what that snapshot archived -- deletions/renames bump
        no mtime, so mtime alone would never back them up (and a later
        restore would resurrect deleted files).

        Known accepted edge: on coarse-mtime filesystems a write landing in
        the same clock second the snapshot started can be missed until the
        next change/shutdown snapshot. A ``>=`` comparison would close it but
        causes infinite re-snapshot churn when mtimes equal the baseline.
        """
        latest, names = self._scan()
        if latest > self.last_backup_at:
            return True
        return self._last_archive_names is not None and names != self._last_archive_names

    async def watch(self, interval_seconds: int | None = None) -> None:
        """Periodic loop: snapshot whenever the data dir changed. Cancellable."""
        interval = interval_seconds or get_settings().backup_interval_seconds
        logger.info("Backup watcher started (every %ds -> %s)", interval, self.repo_id)
        while True:
            await asyncio.sleep(interval)
            try:
                if await asyncio.to_thread(self.dirty):
                    await self.backup()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Backup watcher iteration failed: %s", exc)


# Module-level singleton: shared state (last_backup_at) across requests/tasks.
_service: BackupService | None = None


def get_backup_service() -> BackupService:
    global _service
    if _service is None:
        _service = BackupService()
    return _service
