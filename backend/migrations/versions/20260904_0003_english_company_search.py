"""add normalized English company name

Revision ID: 20260904_0003
Revises: 20260904_0002
Create Date: 2026-09-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0003"
down_revision: str | Sequence[str] | None = "20260904_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("normalized_eng_name", sa.String(300), nullable=True))
    op.create_index("ix_companies_normalized_eng_name", "companies", ["normalized_eng_name"])


def downgrade() -> None:
    op.drop_index("ix_companies_normalized_eng_name", table_name="companies")
    op.drop_column("companies", "normalized_eng_name")
