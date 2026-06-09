"""add historical_prices table

Revision ID: c7e1a2f3b4d5
Revises: b3cf18d92e0a
Create Date: 2026-06-10 00:00:00.000000

Net-new corpus table for Phase 13 historical-learning price suggestions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e1a2f3b4d5'
down_revision: Union[str, None] = 'b3cf18d92e0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("trade_category", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_project_id", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_historical_prices_id"), "historical_prices", ["id"])
    op.create_index(op.f("ix_historical_prices_trade_category"), "historical_prices", ["trade_category"])
    op.create_index(op.f("ix_historical_prices_source_project_id"), "historical_prices", ["source_project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_historical_prices_source_project_id"), table_name="historical_prices")
    op.drop_index(op.f("ix_historical_prices_trade_category"), table_name="historical_prices")
    op.drop_index(op.f("ix_historical_prices_id"), table_name="historical_prices")
    op.drop_table("historical_prices")
