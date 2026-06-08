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
