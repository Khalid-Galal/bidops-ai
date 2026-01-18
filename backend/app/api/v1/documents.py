"""Document endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.auth.permissions import Permission, check_permission
from app.models import Document, Project
from app.models.base import DocumentCategory, DocumentStatus
from app.schemas.common import PaginatedResponse
from app.schemas.document import (
    DocumentContentResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResult,
    DocumentUploadResponse,
)

router = APIRouter()


@router.get("/project/{project_id}", response_model=PaginatedResponse[DocumentListResponse])
async def list_project_documents(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[DocumentStatus] = None,
    category_filter: Optional[DocumentCategory] = None,
    file_type: Optional[str] = None,
) -> PaginatedResponse[DocumentListResponse]:
    """List documents for a project.

    Args:
        project_id: Project ID
        db: Database session
        current_user: Authenticated user
        page: Page number
        page_size: Items per page
        status_filter: Filter by status
        category_filter: Filter by category
        file_type: Filter by file type (pdf, docx, etc.)

    Returns:
        Paginated list of documents
    """
    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Base query
    query = select(Document).where(Document.project_id == project_id)

    # Apply filters
    if status_filter:
        query = query.where(Document.status == status_filter)
    if category_filter:
        query = query.where(Document.category == category_filter)
    if file_type:
        query = query.where(Document.file_type == file_type.lower())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated results
    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    documents = result.scalars().all()

    return PaginatedResponse.create(
        items=[DocumentListResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentResponse:
    """Get document by ID.

    Args:
        document_id: Document ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Document details

    Raises:
        HTTPException: If document not found
    """
    result = await db.execute(
        select(Document)
        .join(Project)
        .where(
            Document.id == document_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentContentResponse:
    """Get document extracted content.

    Args:
        document_id: Document ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Document content

    Raises:
        HTTPException: If document not found
    """
    result = await db.execute(
        select(Document)
        .join(Project)
        .where(
            Document.id == document_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentContentResponse(
        id=document.id,
        filename=document.filename,
        extracted_text=document.extracted_text,
        page_count=document.page_count,
        metadata=document.metadata,
    )


@router.post("/project/{project_id}/upload", response_model=DocumentUploadResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> DocumentUploadResponse:
    """Upload a document to a project.

    Args:
        project_id: Project ID
        file: File to upload
        db: Database session
        current_user: Authenticated user

    Returns:
        Upload result

    Raises:
        HTTPException: If project not found or permission denied
    """
    if not check_permission(current_user.role, Permission.DOCUMENT_UPLOAD):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Validate file type
    allowed_extensions = {
        "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt",
        "txt", "msg", "eml", "dxf", "dwg", "ifc", "xer", "xml",
        "png", "jpg", "jpeg", "tiff", "bmp", "gif", "zip"
    }
    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed: {file_ext}",
        )

    # In production, save file and create document record
    # For now, return placeholder
    return DocumentUploadResponse(
        id=0,
        filename=file.filename or "unknown",
        status=DocumentStatus.PENDING,
        message="Document queued for processing",
    )


@router.post("/search", response_model=list[DocumentSearchResult])
async def search_documents(
    request: DocumentSearchRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[DocumentSearchResult]:
    """Semantic search across documents.

    Args:
        request: Search parameters
        db: Database session
        current_user: Authenticated user

    Returns:
        List of matching document chunks
    """
    # In production, this would query Qdrant vector store
    # For now, return empty list
    return []


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Delete a document.

    Args:
        document_id: Document ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If document not found or permission denied
    """
    if not check_permission(current_user.role, Permission.DOCUMENT_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    result = await db.execute(
        select(Document)
        .join(Project)
        .where(
            Document.id == document_id,
            Project.organization_id == current_user.organization_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await db.delete(document)
    await db.commit()

    return {"message": "Document deleted successfully"}
