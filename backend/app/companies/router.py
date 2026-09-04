from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.companies.financials import FinancialService
from app.companies.repository import CompanyRepository
from app.companies.models import FilingRecord
from app.companies.schemas import (
    CompanyProfileResponse,
    CompanyResearchResponse,
    CompanySearchResponse,
    CompanySearchResult,
    DocumentExtractionResponse,
    FilingResponse,
    FilingSectionResponse,
    FinancialMetricResponse,
    FinancialSummaryResponse,
)
from app.companies.service import CompanyResearchService
from app.config import Settings
from app.dart import DartClient
from app.database import get_session


router = APIRouter(prefix="/api/companies", tags=["companies"])


def get_dart_client() -> Generator[DartClient, None, None]:
    settings = Settings.from_env()
    with DartClient(settings.dart_api_key, base_url=settings.dart_base_url, timeout=settings.dart_timeout_seconds) as client:
        yield client


@router.get("/search", response_model=CompanySearchResponse)
def search_companies(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> CompanySearchResponse:
    records, total = CompanyRepository(session).search(q, limit=limit, offset=offset)
    return CompanySearchResponse(
        query=q,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(records) < total,
        results=[CompanySearchResult.model_validate(record, from_attributes=True) for record in records],
    )


@router.get("/{corp_code}", response_model=CompanySearchResult)
def get_company(corp_code: str, session: Session = Depends(get_session)) -> CompanySearchResult:
    record = CompanyRepository(session).get(corp_code)
    if record is None:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")
    return CompanySearchResult.model_validate(record, from_attributes=True)


@router.post("/{corp_code}/refresh", response_model=CompanyResearchResponse)
def refresh_company_research(
    corp_code: str,
    session: Session = Depends(get_session),
    dart: DartClient = Depends(get_dart_client),
) -> CompanyResearchResponse:
    company_record = CompanyRepository(session).get(corp_code)
    if company_record is None:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")
    profile, filings = CompanyResearchService(session, dart, Settings.from_env().document_cache_dir).refresh_company(corp_code)
    return CompanyResearchResponse(
        profile=CompanyProfileResponse(
            corp_code=corp_code,
            corp_name=company_record.corp_name,
            stock_code=company_record.stock_code,
            ceo_name=profile.ceo_name,
            corporation_type=profile.corporation_type,
            industry_code=profile.industry_code,
            established_date=profile.established_date,
            accounting_month=profile.accounting_month,
        ),
        filings=[_filing_response(record) for record in filings],
    )


@router.get("/{corp_code}/filings", response_model=list[FilingResponse])
def get_company_filings(corp_code: str, session: Session = Depends(get_session)) -> list[FilingResponse]:
    if CompanyRepository(session).get(corp_code) is None:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")
    return [_filing_response(record) for record in CompanyResearchService(
        session,
        dart=None,
        cache_dir=Settings.from_env().document_cache_dir,
    ).get_filings(corp_code)]


@router.post("/filings/{receipt_number}/extract", response_model=DocumentExtractionResponse)
def extract_filing(
    receipt_number: str,
    session: Session = Depends(get_session),
    dart: DartClient = Depends(get_dart_client),
) -> DocumentExtractionResponse:
    if not receipt_number.isdigit() or len(receipt_number) != 14:
        raise HTTPException(status_code=422, detail="접수번호는 14자리 숫자여야 합니다.")
    if session.get(FilingRecord, receipt_number) is None:
        raise HTTPException(status_code=404, detail="먼저 기업 공시목록을 갱신해 주세요.")
    service = CompanyResearchService(session, dart, Settings.from_env().document_cache_dir)
    cache, sections = service.cache_and_extract(receipt_number)
    return DocumentExtractionResponse(
        receipt_number=receipt_number,
        byte_size=cache.byte_size,
        sha256=cache.sha256,
        sections=[FilingSectionResponse(
            order=section.section_order,
            title=section.title,
            text_preview=section.text[:500],
            source_element_id=section.source_element_id,
        ) for section in sections],
    )


@router.post("/{corp_code}/financials/refresh", response_model=FinancialSummaryResponse)
def refresh_financials(
    corp_code: str,
    business_year: Annotated[str, Query(pattern=r"^\d{4}$")],
    report_code: Annotated[str, Query(pattern=r"^1101[1-4]$")],
    session: Session = Depends(get_session),
    dart: DartClient = Depends(get_dart_client),
) -> FinancialSummaryResponse:
    if CompanyRepository(session).get(corp_code) is None:
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다.")
    records = FinancialService(session, dart).refresh(corp_code, business_year, report_code)
    return _financial_response(corp_code, business_year, report_code, records)


@router.get("/{corp_code}/financials", response_model=FinancialSummaryResponse)
def get_financials(
    corp_code: str,
    business_year: Annotated[str, Query(pattern=r"^\d{4}$")],
    report_code: Annotated[str, Query(pattern=r"^1101[1-4]$")],
    session: Session = Depends(get_session),
) -> FinancialSummaryResponse:
    records = FinancialService(session, dart=None).get(corp_code, business_year, report_code)
    return _financial_response(corp_code, business_year, report_code, records)


def _filing_response(record: object) -> FilingResponse:
    receipt_number = str(getattr(record, "receipt_number"))
    return FilingResponse(
        receipt_number=receipt_number,
        report_name=str(getattr(record, "report_name")),
        receipt_date=str(getattr(record, "receipt_date")),
        remarks=getattr(record, "remarks"),
        viewer_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_number}",
    )


_METRIC_LABELS = {
    "assets": "자산",
    "liabilities": "부채",
    "equity": "자본",
    "revenue": "매출",
    "operating_income": "영업이익",
    "net_income": "순이익",
}


def _financial_response(corp_code: str, business_year: str, report_code: str, records: list[object]) -> FinancialSummaryResponse:
    metrics = []
    for record in records:
        current = int(getattr(record, "current_amount"))
        previous_value = getattr(record, "previous_amount")
        previous = int(previous_value) if previous_value is not None else None
        change = round((current - previous) / abs(previous) * 100, 1) if previous not in {None, 0} else None
        code = str(getattr(record, "metric_code"))
        metrics.append(FinancialMetricResponse(
            code=code,
            label=_METRIC_LABELS.get(code, code),
            current_amount=current,
            previous_amount=previous,
            change_percent=change,
            currency=getattr(record, "currency"),
            comparison_basis=str(getattr(record, "comparison_basis")),
        ))
    return FinancialSummaryResponse(
        corp_code=corp_code,
        business_year=business_year,
        report_code=report_code,
        financial_statement_division=str(getattr(records[0], "financial_statement_division")) if records else None,
        metrics=metrics,
    )
