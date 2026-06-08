"""make boq_items.unit nullable

Revision ID: b3cf18d92e0a
Revises: a2bb5607f46c
Create Date: 2026-06-09 00:00:00.000000

The BOQ parser legitimately yields ``unit=None`` for blank-unit lines (lump
sums, provisional sums, sub-totals). The original schema declared
``boq_items.unit`` as NOT NULL, so persisting such a row raised
``IntegrityError: NOT NULL constraint failed`` on both SQLite and Postgres.

This relaxes the column to nullable. Because the target includes SQLite (which
cannot ``ALTER COLUMN`` in place), the change is applied via Alembic batch mode,
which recreates the table with the new constraint.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3cf18d92e0a'
down_revision: Union[str, None] = 'a2bb5607f46c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("boq_items") as batch:
        batch.alter_column("unit", existing_type=sa.String(length=50), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("boq_items") as batch:
        batch.alter_column("unit", existing_type=sa.String(length=50), nullable=False)
