"""add order city address notes

Revision ID: 002
Revises: 001
Create Date: 2026-09-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("orders")}
    if "city" not in cols:
        op.add_column("orders", sa.Column("city", sa.String(120), nullable=True))
    if "address" not in cols:
        op.add_column("orders", sa.Column("address", sa.String(255), nullable=True))
    if "notes" not in cols:
        op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("orders")}
    if "notes" in cols:
        op.drop_column("orders", "notes")
    if "address" in cols:
        op.drop_column("orders", "address")
    if "city" in cols:
        op.drop_column("orders", "city")
