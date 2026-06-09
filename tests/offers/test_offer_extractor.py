import json

import pytest

from app.models.base import OfferStatus
from app.models.boq import BOQItem
from app.models.package import Package
from app.models.project import Project
from app.models.supplier import Supplier, SupplierOffer
from app.schemas.offer import ComplianceAnalysis, OfferExtraction
from app.services.offer.offer_extractor import LLMUnavailable, OfferExtractor


class _FakeLLM:
    def __init__(self, result):
        self._result = result
        self.prompts = []

    def extract(self, prompt, response_model):
        self.prompts.append(prompt)
        return self._result


async def _seed_offer(db, tmp_path, *, checklist=None):
    project = Project(name="Metro")
    if checklist is not None:
        project.checklist_json = json.dumps(checklist)
    db.add(project)
    await db.flush()
    package = Package(project_id=project.id, name="HVAC", code="PKG-001-MEP", trade_category="mep")
    db.add(package)
    await db.flush()
    db.add(BOQItem(project_id=project.id, package_id=package.id, line_number="1",
                   description="Supply chillers", unit="no", quantity=2,
                   client_row_index=1, trade_category="mep"))
    supplier = Supplier(name="CoolAir", emails=["s@coolair.test"], trade_categories=["mep"])
    db.add(supplier)
    await db.flush()
    offer_file = tmp_path / "offer.txt"
    offer_file.write_text("Our price is 150000 USD, validity 90 days, delivery 8 weeks.")
    offer = SupplierOffer(package_id=package.id, supplier_id=supplier.id,
                          status=OfferStatus.RECEIVED.value, file_paths=[str(offer_file)])
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


async def test_extract_offer_populates_fields(db_session, tmp_path):
    offer = await _seed_offer(db_session, tmp_path)
    fake = OfferExtraction(total_price=150000, currency="USD", validity_days=90,
                           delivery_weeks=8, exclusions=["site cleanup"])
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    out = await ex.extract_offer(db_session, offer.id)
    assert out["total_price"] == 150000
    await db_session.refresh(offer)
    assert offer.total_price == 150000
    assert offer.currency == "USD"
    assert offer.delivery_weeks == 8
    assert offer.exclusions == ["site cleanup"]
    assert offer.status == OfferStatus.UNDER_REVIEW.value


async def test_check_compliance_sets_status_and_fields(db_session, tmp_path):
    checklist = {"requirements": [{"requirement": "ISO 9001 certificate"}],
                 "submission_documents": [], "eligibility_criteria": []}
    offer = await _seed_offer(db_session, tmp_path, checklist=checklist)
    fake = ComplianceAnalysis(overall_compliance="NON_COMPLIANT", compliance_score=40,
                              missing_items=["ISO 9001 certificate"],
                              clarifications_needed=["Provide ISO 9001 cert"])
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    out = await ex.check_compliance(db_session, offer.id)
    assert out["overall_compliance"] == "NON_COMPLIANT"
    await db_session.refresh(offer)
    assert offer.status == OfferStatus.NON_COMPLIANT.value
    assert offer.clarifications_needed == ["Provide ISO 9001 cert"]
    assert offer.compliance_analysis["compliance_score"] == 40


async def test_compliance_compliant_status(db_session, tmp_path):
    offer = await _seed_offer(db_session, tmp_path, checklist={"requirements": [], "submission_documents": [], "eligibility_criteria": []})
    fake = ComplianceAnalysis(overall_compliance="COMPLIANT", compliance_score=95)
    ex = OfferExtractor(llm_service=_FakeLLM(fake))
    await ex.check_compliance(db_session, offer.id)
    await db_session.refresh(offer)
    assert offer.status == OfferStatus.COMPLIANT.value


async def test_extract_raises_when_llm_unavailable(db_session, tmp_path, monkeypatch):
    offer = await _seed_offer(db_session, tmp_path)
    ex = OfferExtractor()
    monkeypatch.setattr(ex, "_resolve_llm", lambda: None)
    with pytest.raises(LLMUnavailable):
        await ex.extract_offer(db_session, offer.id)


async def test_extract_unknown_offer_raises(db_session):
    ex = OfferExtractor(llm_service=_FakeLLM(OfferExtraction()))
    with pytest.raises(ValueError):
        await ex.extract_offer(db_session, 999999)
