"""add api usage buckets for anonymous session limits

Revision ID: 20260909_0007
Revises: 20260906_0006
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_0007"
down_revision: str | None = "20260906_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_usage_buckets",
        sa.Column("bucket_key", sa.String(length=128), primary_key=True),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_usage_buckets_expires_at", "api_usage_buckets", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "api_usage_buckets" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_api_usage_buckets_expires_at", table_name="api_usage_buckets")
    op.drop_table("api_usage_buckets")
