from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyRecord(Base):
    __tablename__ = "companies"

    corp_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    corp_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    corp_eng_name: Mapped[str | None] = mapped_column(String(300))
    normalized_eng_name: Mapped[str | None] = mapped_column(String(300))
    stock_code: Mapped[str | None] = mapped_column(String(6), index=True)
    modify_date: Mapped[str] = mapped_column(String(8), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_companies_normalized_name", "normalized_name"),
        Index("ix_companies_normalized_eng_name", "normalized_eng_name"),
    )


class CompanySyncRecord(Base):
    __tablename__ = "company_syncs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    company_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500))


class CompanyProfileRecord(Base):
    __tablename__ = "company_profiles"

    corp_code: Mapped[str] = mapped_column(ForeignKey("companies.corp_code", ondelete="CASCADE"), primary_key=True)
    ceo_name: Mapped[str | None] = mapped_column(String(200))
    corporation_type: Mapped[str | None] = mapped_column(String(1))
    business_number: Mapped[str | None] = mapped_column(String(20))
    industry_code: Mapped[str | None] = mapped_column(String(20))
    established_date: Mapped[str | None] = mapped_column(String(8))
    accounting_month: Mapped[str | None] = mapped_column(String(2))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FilingRecord(Base):
    __tablename__ = "filings"

    receipt_number: Mapped[str] = mapped_column(String(14), primary_key=True)
    corp_code: Mapped[str] = mapped_column(ForeignKey("companies.corp_code", ondelete="CASCADE"), index=True)
    corporation_class: Mapped[str] = mapped_column(String(1))
    report_name: Mapped[str] = mapped_column(String(500))
    filer_name: Mapped[str] = mapped_column(String(200))
    receipt_date: Mapped[str] = mapped_column(String(8), index=True)
    remarks: Mapped[str | None] = mapped_column(String(100))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentCacheRecord(Base):
    __tablename__ = "document_caches"

    receipt_number: Mapped[str] = mapped_column(ForeignKey("filings.receipt_number", ondelete="CASCADE"), primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FilingSectionRecord(Base):
    __tablename__ = "filing_sections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    receipt_number: Mapped[str] = mapped_column(ForeignKey("filings.receipt_number", ondelete="CASCADE"), index=True)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_element_id: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (UniqueConstraint("receipt_number", "section_order"),)


class FinancialMetricRecord(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    corp_code: Mapped[str] = mapped_column(ForeignKey("companies.corp_code", ondelete="CASCADE"), index=True)
    business_year: Mapped[str] = mapped_column(String(4), nullable=False)
    report_code: Mapped[str] = mapped_column(String(5), nullable=False)
    financial_statement_division: Mapped[str] = mapped_column(String(3), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str] = mapped_column(String(200), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    current_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_amount: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(10))
    comparison_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("corp_code", "business_year", "report_code", "metric_code"),)


class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    corp_code: Mapped[str] = mapped_column(ForeignKey("companies.corp_code", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApiUsageBucketRecord(Base):
    __tablename__ = "api_usage_buckets"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_api_usage_buckets_expires_at", "expires_at"),)
