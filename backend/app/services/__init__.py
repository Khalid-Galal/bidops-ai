"""Core services module.

Services are imported lazily to avoid circular import issues.
Import directly from the service module when needed:
    from app.services.document_service import DocumentService
"""

__all__ = [
    "VectorStoreService",
    "DocumentService",
    "LLMService",
    "LLMProvider",
    "ExtractionService",
    "BOQService",
    "PackagingService",
    "SupplierService",
    "EmailService",
    "OfferService",
    "PricingService",
    "ExportService",
]


def __getattr__(name: str):
    """Lazy import services to avoid circular imports."""
    if name == "VectorStoreService":
        from app.services.vector_store import VectorStoreService
        return VectorStoreService
    elif name == "DocumentService":
        from app.services.document_service import DocumentService
        return DocumentService
    elif name == "LLMService":
        from app.services.llm_service import LLMService
        return LLMService
    elif name == "LLMProvider":
        from app.services.llm_service import LLMProvider
        return LLMProvider
    elif name == "ExtractionService":
        from app.services.extraction_service import ExtractionService
        return ExtractionService
    elif name == "BOQService":
        from app.services.boq_service import BOQService
        return BOQService
    elif name == "PackagingService":
        from app.services.packaging_service import PackagingService
        return PackagingService
    elif name == "SupplierService":
        from app.services.supplier_service import SupplierService
        return SupplierService
    elif name == "EmailService":
        from app.services.email_service import EmailService
        return EmailService
    elif name == "OfferService":
        from app.services.offer_service import OfferService
        return OfferService
    elif name == "PricingService":
        from app.services.pricing_service import PricingService
        return PricingService
    elif name == "ExportService":
        from app.services.export_service import ExportService
        return ExportService
    raise AttributeError(f"module 'app.services' has no attribute '{name}'")
