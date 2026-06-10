"""document classification + versioning columns

Revision ID: d4f8b2c9e1a7
Revises: c7e1a2f3b4d5
Create Date: 2026-06-10 12:00:00.000000

Additive columns for Phase 7C (classification, content-hash dedup,
addenda-supersedes versioning). superseded_by_id is intentionally a plain
indexed Integer (no FK): SQLite cannot add an FK to an existing table without
a full rebuild, and FK enforcement is off anyway.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f8b2c9e1a7'
down_revision: Union[str, None] = 'c7e1a2f3b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("category", sa.String(length=20), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("superseded_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("version_label", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("supersede_reason", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_documents_content_hash"), "documents", ["content_hash"])
    op.create_index(op.f("ix_documents_superseded_by_id"), "documents", ["superseded_by_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_superseded_by_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_content_hash"), table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("supersede_reason")
        batch.drop_column("version_label")
        batch.drop_column("superseded_by_id")
        batch.drop_column("is_superseded")
        batch.drop_column("content_hash")
        batch.drop_column("category")
