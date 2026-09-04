from datetime import UTC, datetime
import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.companies.models import CompanyRecord, CompanySyncRecord
from app.dart.models import CompanySummary


_CORPORATE_MARKERS = re.compile(r"(?:주식회사|\(주\)|㈜)|\s+")
_SEARCH_SEPARATORS = re.compile(r"[\W_]+", flags=re.UNICODE)


def normalize_company_name(name: str) -> str:
    normalized = _CORPORATE_MARKERS.sub("", name).casefold()
    return normalized.replace("씨앤", "씨엔")


def normalize_english_name(name: str | None) -> str | None:
    if not name:
        return None
    return _SEARCH_SEPARATORS.sub("", name).casefold() or None


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, *, limit: int = 20, offset: int = 0) -> tuple[list[CompanyRecord], int]:
        normalized = normalize_company_name(query)
        normalized_english = normalize_english_name(query)
        if not normalized:
            return [], 0
        stock_query = query.strip()
        name_terms = {normalized}
        if normalized == "lg":
            name_terms.add("엘지")
        elif normalized == "엘지":
            name_terms.add("lg")

        exact_conditions = [CompanyRecord.normalized_name.in_(name_terms), CompanyRecord.stock_code == stock_query]
        prefix_conditions = [or_(*(CompanyRecord.normalized_name.startswith(term) for term in name_terms))]
        search_conditions = [or_(*(CompanyRecord.normalized_name.contains(term) for term in name_terms)), CompanyRecord.stock_code.startswith(stock_query)]
        if normalized_english:
            exact_conditions.append(CompanyRecord.normalized_eng_name == normalized_english)
            prefix_conditions.append(CompanyRecord.normalized_eng_name.startswith(normalized_english))
            if len(normalized_english) <= 2:
                search_conditions.append(CompanyRecord.normalized_eng_name.startswith(normalized_english))
            else:
                search_conditions.append(CompanyRecord.normalized_eng_name.contains(normalized_english))
        predicate = (CompanyRecord.stock_code.is_not(None) & or_(*search_conditions))
        rank = case(
            (or_(*exact_conditions), 0),
            (or_(*prefix_conditions), 1),
            else_=2,
        )
        statement = (
            select(CompanyRecord)
            .where(predicate)
            .order_by(rank, CompanyRecord.stock_code.is_(None), func.length(CompanyRecord.corp_name), CompanyRecord.corp_name)
            .offset(offset)
            .limit(limit)
        )
        total = self._session.scalar(select(func.count()).select_from(CompanyRecord).where(predicate)) or 0
        return list(self._session.scalars(statement)), total

    def get(self, corp_code: str) -> CompanyRecord | None:
        return self._session.get(CompanyRecord, corp_code)

    def sync(self, companies: list[CompanySummary], *, batch_size: int = 1000) -> int:
        now = datetime.now(UTC)
        values = [
            {
                "corp_code": company.corp_code,
                "corp_name": company.corp_name,
                "normalized_name": normalize_company_name(company.corp_name),
                "corp_eng_name": company.corp_eng_name,
                "normalized_eng_name": normalize_english_name(company.corp_eng_name),
                "stock_code": company.stock_code,
                "modify_date": company.modify_date,
                "synced_at": now,
            }
            for company in companies
        ]
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        for start in range(0, len(values), batch_size):
            batch = values[start:start + batch_size]
            if dialect == "sqlite":
                statement = sqlite_insert(CompanyRecord).values(batch)
                statement = statement.on_conflict_do_update(
                    index_elements=[CompanyRecord.corp_code],
                    set_={
                        "corp_name": statement.excluded.corp_name,
                        "normalized_name": statement.excluded.normalized_name,
                        "corp_eng_name": statement.excluded.corp_eng_name,
                        "normalized_eng_name": statement.excluded.normalized_eng_name,
                        "stock_code": statement.excluded.stock_code,
                        "modify_date": statement.excluded.modify_date,
                        "synced_at": statement.excluded.synced_at,
                    },
                )
                self._session.execute(statement)
            else:
                for item in batch:
                    self._session.merge(CompanyRecord(**item))
            self._session.commit()
        return len(values)

    def start_sync(self) -> CompanySyncRecord:
        record = CompanySyncRecord(started_at=datetime.now(UTC), status="running", company_count=0)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def finish_sync(self, record: CompanySyncRecord, *, company_count: int) -> None:
        record.status = "completed"
        record.company_count = company_count
        record.completed_at = datetime.now(UTC)
        self._session.commit()

    def fail_sync(self, record: CompanySyncRecord, error: Exception) -> None:
        record.status = "failed"
        record.error_message = str(error)[:500]
        record.completed_at = datetime.now(UTC)
        self._session.commit()
