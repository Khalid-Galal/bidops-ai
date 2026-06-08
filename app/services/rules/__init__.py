"""Rules configuration service package."""

from functools import lru_cache

from app.services.rules.rules_service import RulesService


@lru_cache
def get_rules_service() -> RulesService:
    """Cached default RulesService (defaults + data/rules.json)."""
    return RulesService()


__all__ = ["RulesService", "get_rules_service"]
