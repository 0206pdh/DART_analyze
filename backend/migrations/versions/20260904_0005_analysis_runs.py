"""add analysis runs

Revision ID: 20260904_0005
Revises: 20260904_0004
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0005"
down_revision: str | None = "20260904_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("corp_code", sa.String(length=8), sa.ForeignKey("companies.corp_code", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analysis_runs_corp_code", "analysis_runs", ["corp_code"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_corp_code", table_name="analysis_runs")
    op.drop_table("analysis_runs")
