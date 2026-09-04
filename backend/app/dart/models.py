from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompanySummary:
    corp_code: str
    corp_name: str
    corp_eng_name: str | None
    stock_code: str | None
    modify_date: str


@dataclass(frozen=True, slots=True)
class Company:
    corp_code: str
    corp_name: str
    corp_name_eng: str | None
    stock_name: str | None
    stock_code: str | None
    ceo_name: str | None
    corporation_type: str | None
    business_number: str | None
    industry_code: str | None
    established_date: str | None
    accounting_month: str | None


@dataclass(frozen=True, slots=True)
class Disclosure:
    receipt_number: str
    corporation_class: str
    corporation_name: str
    corporation_code: str
    stock_code: str | None
    report_name: str
    filer_name: str
    receipt_date: str
    remarks: str | None

    @property
    def viewer_url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.receipt_number}"


@dataclass(frozen=True, slots=True)
class DocumentFile:
    name: str
    size: int
    root_tag: str | None
    encoding: str | None
    title_samples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentArchive:
    files: tuple[DocumentFile, ...]

    @property
    def xml_file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True, slots=True)
class ExtractedSection:
    order: int
    title: str
    text: str
    source_element_id: str | None


@dataclass(frozen=True, slots=True)
class FinancialAccount:
    receipt_number: str
    business_year: str
    report_code: str
    statement_division: str
    account_id: str
    account_name: str
    current_amount: str | None
    current_cumulative_amount: str | None
    previous_amount: str | None
    previous_quarter_amount: str | None
    previous_cumulative_amount: str | None
    currency: str | None
    order: int
