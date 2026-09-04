"""create company research cache

Revision ID: 20260904_0002
Revises: 20260904_0001
Create Date: 2026-09-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0002"
down_revision: str | Sequence[str] | None = "20260904_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("corp_code", sa.String(8), nullable=False),
        sa.Column("ceo_name", sa.String(200)),
        sa.Column("corporation_type", sa.String(1)),
        sa.Column("business_number", sa.String(20)),
        sa.Column("industry_code", sa.String(20)),
        sa.Column("established_date", sa.String(8)),
        sa.Column("accounting_month", sa.String(2)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corp_code"], ["companies.corp_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("corp_code"),
    )
    op.create_table(
        "filings",
        sa.Column("receipt_number", sa.String(14), nullable=False),
        sa.Column("corp_code", sa.String(8), nullable=False),
        sa.Column("corporation_class", sa.String(1), nullable=False),
        sa.Column("report_name", sa.String(500), nullable=False),
        sa.Column("filer_name", sa.String(200), nullable=False),
        sa.Column("receipt_date", sa.String(8), nullable=False),
        sa.Column("remarks", sa.String(100)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corp_code"], ["companies.corp_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("receipt_number"),
    )
    op.create_index("ix_filings_corp_code", "filings", ["corp_code"])
    op.create_index("ix_filings_receipt_date", "filings", ["receipt_date"])
    op.create_table(
        "document_caches",
        sa.Column("receipt_number", sa.String(14), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["receipt_number"], ["filings.receipt_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("receipt_number"),
    )
    op.create_table(
        "filing_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_number", sa.String(14), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_element_id", sa.String(50)),
        sa.ForeignKeyConstraint(["receipt_number"], ["filings.receipt_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_number", "section_order"),
    )
    op.create_index("ix_filing_sections_receipt_number", "filing_sections", ["receipt_number"])


def downgrade() -> None:
    op.drop_index("ix_filing_sections_receipt_number", table_name="filing_sections")
    op.drop_table("filing_sections")
    op.drop_table("document_caches")
    op.drop_index("ix_filings_receipt_date", table_name="filings")
    op.drop_index("ix_filings_corp_code", table_name="filings")
    op.drop_table("filings")
    op.drop_table("company_profiles")
