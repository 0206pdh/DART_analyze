from pydantic import BaseModel, Field


class CompanySearchResult(BaseModel):
    corp_code: str
    corp_name: str
    corp_eng_name: str | None
    stock_code: str | None
    modify_date: str


class CompanySearchResponse(BaseModel):
    query: str
    total: int
    limit: int
    offset: int
    has_more: bool
    results: list[CompanySearchResult]


class CompanySearchParams(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class CompanyProfileResponse(BaseModel):
    corp_code: str
    corp_name: str
    stock_code: str | None
    ceo_name: str | None
    corporation_type: str | None
    industry_code: str | None
    established_date: str | None
    accounting_month: str | None


class FilingResponse(BaseModel):
    receipt_number: str
    report_name: str
    receipt_date: str
    remarks: str | None
    viewer_url: str


class CompanyResearchResponse(BaseModel):
    profile: CompanyProfileResponse
    filings: list[FilingResponse]


class FilingSectionResponse(BaseModel):
    order: int
    title: str
    text_preview: str
    source_element_id: str | None


class DocumentExtractionResponse(BaseModel):
    receipt_number: str
    byte_size: int
    sha256: str
    sections: list[FilingSectionResponse]


class FinancialMetricResponse(BaseModel):
    code: str
    label: str
    current_amount: int
    previous_amount: int | None
    change_percent: float | None
    currency: str | None
    comparison_basis: str


class FinancialSummaryResponse(BaseModel):
    corp_code: str
    business_year: str
    report_code: str
    financial_statement_division: str | None
    metrics: list[FinancialMetricResponse]
