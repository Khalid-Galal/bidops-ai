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
