"""create financial metrics

Revision ID: 20260904_0004
Revises: 20260904_0003
Create Date: 2026-09-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0004"
down_revision: str | Sequence[str] | None = "20260904_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("corp_code", sa.String(8), nullable=False),
        sa.Column("business_year", sa.String(4), nullable=False),
        sa.Column("report_code", sa.String(5), nullable=False),
        sa.Column("financial_statement_division", sa.String(3), nullable=False),
        sa.Column("metric_code", sa.String(30), nullable=False),
        sa.Column("account_id", sa.String(200), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("current_amount", sa.BigInteger(), nullable=False),
        sa.Column("previous_amount", sa.BigInteger()),
        sa.Column("currency", sa.String(10)),
        sa.Column("comparison_basis", sa.String(30), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corp_code"], ["companies.corp_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corp_code", "business_year", "report_code", "metric_code"),
    )
    op.create_index("ix_financial_metrics_corp_code", "financial_metrics", ["corp_code"])


def downgrade() -> None:
    op.drop_index("ix_financial_metrics_corp_code", table_name="financial_metrics")
    op.drop_table("financial_metrics")
