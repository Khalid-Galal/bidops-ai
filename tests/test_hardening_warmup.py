"""Phase 15: settings + model warmup."""
from __future__ import annotations

from app.config import Settings


def test_hardening_settings_have_safe_defaults():
    s = Settings()
    # New NFR knobs exist with conservative defaults.
    assert s.app_version  # non-empty version string
    assert s.rate_limit_enabled is False          # off by default -> zero UX risk
    assert s.rate_limit_per_minute == 120          # lenient default when enabled
    assert s.rate_limit_burst == 30
    assert s.warmup_models_on_startup is False      # tests/pure-pricing users unaffected
