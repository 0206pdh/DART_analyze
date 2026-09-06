from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.companies.models import FinancialMetricRecord
from app.dart import DartClient, FinancialAccount


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    code: str
    statement_division: str
    account_ids: tuple[str, ...]
    account_names: tuple[str, ...]


METRICS = (
    MetricDefinition("assets", "BS", ("ifrs-full_Assets",), ("자산총계",)),
    MetricDefinition("liabilities", "BS", ("ifrs-full_Liabilities",), ("부채총계",)),
    MetricDefinition("equity", "BS", ("ifrs-full_Equity",), ("자본총계",)),
    MetricDefinition("revenue", "IS", ("ifrs-full_Revenue",), ("매출액", "영업수익")),
    MetricDefinition("operating_income", "IS", ("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)")),
    MetricDefinition("net_income", "IS", ("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "반기순이익", "분기순이익")),
)


class FinancialService:
    def __init__(self, session: Session, dart: DartClient | None) -> None:
        self._session = session
        self._dart = dart

    def refresh(self, corp_code: str, business_year: str, report_code: str) -> list[FinancialMetricRecord]:
        if self._dart is None:
            raise RuntimeError("DART 클라이언트가 필요한 작업입니다.")
        division = "CFS"
        accounts = self._dart.get_financial_statements(corp_code, business_year, report_code, financial_statement_division=division)
        if not accounts:
            division = "OFS"
            accounts = self._dart.get_financial_statements(corp_code, business_year, report_code, financial_statement_division=division)
        now = datetime.now(UTC)
        records: list[FinancialMetricRecord] = []
        for definition in METRICS:
            account = _find_account(accounts, definition)
            if account is None:
                continue
            current, previous, basis = _amounts_for_period(account, report_code)
            if current is None:
                continue
            records.append(FinancialMetricRecord(
                corp_code=corp_code,
                business_year=business_year,
                report_code=report_code,
                financial_statement_division=division,
                metric_code=definition.code,
                account_id=account.account_id,
                account_name=account.account_name,
                current_amount=current,
                previous_amount=previous,
                currency=account.currency,
                comparison_basis=basis,
                fetched_at=now,
            ))
        self._session.execute(delete(FinancialMetricRecord).where(
            FinancialMetricRecord.corp_code == corp_code,
            FinancialMetricRecord.business_year == business_year,
            FinancialMetricRecord.report_code == report_code,
        ))
        self._session.add_all(records)
        self._session.commit()
        return records

    def get(self, corp_code: str, business_year: str, report_code: str) -> list[FinancialMetricRecord]:
        return list(self._session.scalars(select(FinancialMetricRecord).where(
            FinancialMetricRecord.corp_code == corp_code,
            FinancialMetricRecord.business_year == business_year,
            FinancialMetricRecord.report_code == report_code,
        ).order_by(FinancialMetricRecord.id)))

    def get_latest(self, corp_code: str) -> list[FinancialMetricRecord]:
        period = self._session.execute(
            select(FinancialMetricRecord.business_year, FinancialMetricRecord.report_code)
            .where(FinancialMetricRecord.corp_code == corp_code)
            .order_by(FinancialMetricRecord.business_year.desc(), FinancialMetricRecord.report_code.desc())
            .limit(1)
        ).first()
        if period is None:
            return []
        return self.get(corp_code, period.business_year, period.report_code)


def _find_account(accounts: list[FinancialAccount], definition: MetricDefinition) -> FinancialAccount | None:
    candidates = [account for account in accounts if account.statement_division == definition.statement_division]
    by_id = next((account for account in candidates if account.account_id in definition.account_ids), None)
    return by_id or next((account for account in candidates if account.account_name in definition.account_names), None)


def _amounts_for_period(account: FinancialAccount, report_code: str) -> tuple[int | None, int | None, str]:
    if account.statement_division == "BS":
        return _parse_amount(account.current_amount), _parse_amount(account.previous_amount), "전기말 대비"
    if report_code == "11011":
        return _parse_amount(account.current_amount), _parse_amount(account.previous_amount), "전년 대비"
    return (
        _parse_amount(account.current_cumulative_amount or account.current_amount),
        _parse_amount(account.previous_cumulative_amount or account.previous_quarter_amount),
        "전년 동기 누적 대비",
    )


def _parse_amount(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.replace(",", "").strip()
    if not normalized or normalized == "-":
        return None
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return int(normalized)
    except ValueError:
        return None
