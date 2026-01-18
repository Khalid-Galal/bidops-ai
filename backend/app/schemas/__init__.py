"""Pydantic schemas for request/response validation."""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectSummaryField,
    ProjectSummary,
)
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from app.schemas.common import (
    PaginationParams,
    PaginatedResponse,
    MessageResponse,
    ErrorResponse,
)
from app.schemas.package import (
    BOQItemResponse,
    BOQItemUpdate,
    BOQParseRequest,
    BOQParseResponse,
    BOQStatisticsResponse,
    PackageCreate,
    PackageUpdate,
    PackageResponse,
    PackageListResponse,
    PackageGenerateRequest,
    PackageGenerateResponse,
    PackageStatisticsResponse,
)
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierListResponse,
    SupplierImportRequest,
    SupplierImportResponse,
    OfferCreate,
    OfferUpdate,
    OfferResponse,
    OfferListResponse,
    OfferComparisonResponse,
    EmailLogResponse,
)
from app.schemas.pricing import (
    PricePopulateRequest,
    PricePopulateResponse,
    PackageTotalsResponse,
    ProjectTotalsResponse,
    CostBreakdownResponse,
    DashboardResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    "ProjectSummaryField",
    "ProjectSummary",
    # Document
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentSearchRequest",
    "DocumentSearchResult",
    # Package/BOQ
    "BOQItemResponse",
    "BOQItemUpdate",
    "BOQParseRequest",
    "BOQParseResponse",
    "BOQStatisticsResponse",
    "PackageCreate",
    "PackageUpdate",
    "PackageResponse",
    "PackageListResponse",
    "PackageGenerateRequest",
    "PackageGenerateResponse",
    "PackageStatisticsResponse",
    # Supplier/Offer
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierResponse",
    "SupplierListResponse",
    "SupplierImportRequest",
    "SupplierImportResponse",
    "OfferCreate",
    "OfferUpdate",
    "OfferResponse",
    "OfferListResponse",
    "OfferComparisonResponse",
    "EmailLogResponse",
    # Pricing/Export
    "PricePopulateRequest",
    "PricePopulateResponse",
    "PackageTotalsResponse",
    "ProjectTotalsResponse",
    "CostBreakdownResponse",
    "DashboardResponse",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "ErrorResponse",
]
