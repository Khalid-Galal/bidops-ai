import pytest
from sqlalchemy import select

from app.models.document import Document


async def test_document_versioning_columns_persist(db_session):
    doc = Document(
        project_id=1, filename="Spec_RevB.pdf", file_path="/t/s.pdf",
        file_type="pdf", file_size=1,
        category="specs", content_hash="ab" * 32,
        is_superseded=True, superseded_by_id=99,
        version_label="rev B", supersede_reason="auto:test",
    )
    db_session.add(doc)
    await db_session.commit()
    got = (await db_session.execute(select(Document))).scalar_one()
    assert got.category == "specs"
    assert got.is_superseded is True
    assert got.superseded_by_id == 99
    assert got.version_label == "rev B"
    assert got.supersede_reason == "auto:test"
