"""enable row level security on all tables (Postgres only)

Revision ID: 20260906_0006
Revises: 20260904_0005

앱은 Postgres `postgres` 역할(BYPASSRLS)로 직접 접속하므로 영향이 없다.
정책을 만들지 않으므로 `anon`/`authenticated` 역할(Data API)에는 전면 차단이 적용된다.
SQLite 로컬 개발에서는 아무 것도 하지 않는다.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20260906_0006"
down_revision: str | None = "20260904_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "companies",
    "company_syncs",
    "company_profiles",
    "filings",
    "document_caches",
    "filing_sections",
    "financial_metrics",
    "analysis_runs",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
