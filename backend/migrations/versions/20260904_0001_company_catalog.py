"""create company catalog

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("corp_code", sa.String(length=8), nullable=False),
        sa.Column("corp_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("corp_eng_name", sa.String(length=300), nullable=True),
        sa.Column("stock_code", sa.String(length=6), nullable=True),
        sa.Column("modify_date", sa.String(length=8), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("corp_code"),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])
    op.create_index("ix_companies_stock_code", "companies", ["stock_code"])
    op.create_table(
        "company_syncs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("company_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("company_syncs")
    op.drop_index("ix_companies_stock_code", table_name="companies")
    op.drop_index("ix_companies_normalized_name", table_name="companies")
    op.drop_table("companies")

