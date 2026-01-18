"""Package and BOQ schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.base import PackageStatus


# ============================================================================
# BOQ Schemas
# ============================================================================


class BOQItemBase(BaseModel):
    """Base BOQ item schema."""

    line_number: str
    description: str
    unit: str
    quantity: float = 0.0
    section: Optional[str] = None


class BOQItemCreate(BOQItemBase):
    """Schema for creating a BOQ item."""

    trade_category: Optional[str] = None


class BOQItemUpdate(BaseModel):
    """Schema for updating a BOQ item."""

    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    section: Optional[str] = None
    trade_category: Optional[str] = None
    trade_subcategory: Optional[str] = None
    unit_rate: Optional[float] = None
    total_price: Optional[float] = None
    is_excluded: Optional[bool] = None


class BOQItemResponse(BOQItemBase):
    """BOQ item response."""

    id: int
    project_id: int
    trade_category: Optional[str] = None
    trade_subcategory: Optional[str] = None
    classification_confidence: Optional[float] = None
    package_id: Optional[int] = None
    unit_rate: Optional[float] = None
    total_price: Optional[float] = None
    is_excluded: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BOQParseRequest(BaseModel):
    """Request to parse BOQ from file."""

    file_path: str = Field(..., description="Path to Excel BOQ file")
    sheet_name: Optional[str] = Field(None, description="Specific sheet to parse")
    header_row: int = Field(0, ge=0, description="Row index containing headers")
    column_mapping: Optional[dict[str, list[str]]] = Field(
        None, description="Custom column name mapping"
    )


class BOQParseResponse(BaseModel):
    """Response from BOQ parsing."""

    success: bool
    file: str
    items_parsed: int
    sections_found: int
    statistics: dict


class BOQExportRequest(BaseModel):
    """Request to export BOQ."""

    output_path: Optional[str] = None
    include_pricing: bool = False


class BOQClassifyRequest(BaseModel):
    """Request to classify BOQ items with AI."""

    batch_size: int = Field(20, ge=1, le=100)


class BOQStatisticsResponse(BaseModel):
    """BOQ statistics response."""

    total_items: int
    by_trade: dict[str, int]
    by_section: dict[str, int]


# ============================================================================
# Package Schemas
# ============================================================================


class PackageBase(BaseModel):
    """Base package schema."""

    name: str = Field(..., max_length=255)
    trade_category: str = Field(..., max_length=100)
    description: Optional[str] = None


class PackageCreate(PackageBase):
    """Schema for creating a package."""

    code: Optional[str] = Field(None, max_length=50)
    submission_deadline: Optional[datetime] = None
    submission_instructions: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: Optional[str] = Field(None, max_length=10)


class PackageUpdate(BaseModel):
    """Schema for updating a package."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[PackageStatus] = None
    submission_deadline: Optional[datetime] = None
    submission_instructions: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: Optional[str] = Field(None, max_length=10)


class PackageListResponse(BaseModel):
    """Package list item response."""

    id: int
    project_id: int
    name: str
    code: str
    trade_category: str
    status: PackageStatus
    total_items: int
    offers_received: int
    submission_deadline: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PackageResponse(PackageListResponse):
    """Full package response."""

    description: Optional[str] = None
    submission_instructions: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: Optional[str] = None
    folder_path: Optional[str] = None
    brief_path: Optional[str] = None
    offers_evaluated: int = 0
    updated_at: datetime

    model_config = {"from_attributes": True}


class PackageGenerateRequest(BaseModel):
    """Request to auto-generate packages from BOQ."""

    grouping: str = Field("trade", pattern="^(trade|section)$")
    min_items: int = Field(5, ge=1)
    max_items: int = Field(100, ge=10)


class PackageGenerateResponse(BaseModel):
    """Response from package generation."""

    packages_created: int
    packages: list[dict]
    message: Optional[str] = None


class PackageLinkDocumentsRequest(BaseModel):
    """Request to link documents to a package."""

    auto_link: bool = Field(True, description="Automatically find relevant documents")
    document_ids: Optional[list[int]] = Field(None, description="Specific document IDs to link")


class PackageLinkDocumentsResponse(BaseModel):
    """Response from document linking."""

    package_id: int
    documents_linked: int
    document_ids: list[int]


class PackageFolderRequest(BaseModel):
    """Request to create package folder structure."""

    base_path: Optional[str] = None


class PackageFolderResponse(BaseModel):
    """Response from folder creation."""

    package_id: int
    folder_path: str
    boq_file: str
    documents_copied: int


class PackageBriefRequest(BaseModel):
    """Request to generate package brief."""

    output_path: Optional[str] = None


class PackageBriefResponse(BaseModel):
    """Response from brief generation."""

    package_id: int
    brief_path: str


class PackageStatisticsResponse(BaseModel):
    """Package statistics for a project."""

    total_packages: int
    by_status: dict[str, int]
    total_boq_items: int
    assigned_items: int
    unassigned_items: int
    assignment_rate: float


class PackageDocumentResponse(BaseModel):
    """Package-document link response."""

    id: int
    package_id: int
    document_id: int
    relevance_score: Optional[float] = None
    relevance_reason: Optional[str] = None
    include_in_package: bool = True

    model_config = {"from_attributes": True}
