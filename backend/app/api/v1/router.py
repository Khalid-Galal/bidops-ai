"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    projects,
    documents,
    health,
    extraction,
    packages,
    suppliers,
    offers,
    pricing,
)

# Create main v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(extraction.router, prefix="/ai", tags=["ai-extraction"])
api_router.include_router(packages.router, tags=["packages", "boq"])
api_router.include_router(suppliers.router, tags=["suppliers", "emails"])
api_router.include_router(offers.router, tags=["offers", "evaluation"])
api_router.include_router(pricing.router, tags=["pricing", "export", "dashboard"])
