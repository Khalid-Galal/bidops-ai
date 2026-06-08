def test_v2_enums_present():
    from app.models.base import (
        TimestampMixin, DocumentCategory, PackageStatus,
        OfferStatus, EmailType, EmailStatus, UserRole,
    )
    assert PackageStatus.DRAFT.value == "draft"
    assert OfferStatus.SELECTED.value == "selected"
    assert UserRole.ESTIMATOR.value == "estimator"
    assert EmailType.RFQ.value == "rfq"
    assert EmailStatus.SENT.value == "sent"
    assert DocumentCategory.BOQ.value == "boq"
    assert hasattr(TimestampMixin, "created_at")
