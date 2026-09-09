from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.companies.models import (
    CompanyProfileRecord,
    CompanyRecord,
    FilingRecord,
    FinancialMetricRecord,
)
from app.database import Base, get_session
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "true")
    monkeypatch.setenv("APP_SESSION_SECRET", "test-session-secret")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as seed:
        seed.add(CompanyRecord(corp_code="00126380", corp_name="삼성전자", normalized_name="삼성전자", corp_eng_name=None, normalized_eng_name=None, stock_code="005930", modify_date="20260101"))
        seed.add(CompanyRecord(corp_code="00999999", corp_name="비프리로드", normalized_name="비프리로드", corp_eng_name=None, normalized_eng_name=None, stock_code="099999", modify_date="20260101"))
        seed.add(CompanyProfileRecord(corp_code="00126380", ceo_name="전영현", corporation_type="Y", business_number=None, industry_code="264", established_date="19690113", accounting_month="12", fetched_at=datetime.now(UTC)))
        seed.add(FilingRecord(receipt_number="20260814000001", corp_code="00126380", corporation_class="Y", report_name="반기보고서 (2026.06)", filer_name="삼성전자", receipt_date="20260814", remarks=None, fetched_at=datetime.now(UTC)))
        seed.add(FinancialMetricRecord(corp_code="00126380", business_year="2025", report_code="11011", financial_statement_division="CFS", metric_code="revenue", account_id="ifrs-full_Revenue", account_name="수익", current_amount=333605938000000, previous_amount=300870903000000, currency="KRW", comparison_basis="전년 대비", fetched_at=datetime.now(UTC)))
        seed.commit()

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    test_client = TestClient(app)
    assert test_client.get("/api/auth/session").status_code == 200
    yield test_client
    app.dependency_overrides.clear()


def test_refresh_serves_stored_data_without_dart(client):
    response = client.post("/api/companies/00126380/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["ceo_name"] == "전영현"
    assert body["filings"][0]["report_name"] == "반기보고서 (2026.06)"


def test_refresh_returns_409_for_non_preloaded_company(client):
    assert client.post("/api/companies/00999999/refresh").status_code == 409


def test_financials_refresh_falls_back_to_latest_stored_period(client):
    # 프런트가 반기(11012/2026)를 요청해도 저장된 연간(11011/2025)으로 폴백
    response = client.post("/api/companies/00126380/financials/refresh?business_year=2026&report_code=11012")
    assert response.status_code == 200
    body = response.json()
    assert body["business_year"] == "2025"
    assert body["metrics"][0]["code"] == "revenue"


def test_extract_is_forbidden_in_read_only(client):
    assert client.post("/api/companies/filings/20260814000001/extract").status_code == 403
