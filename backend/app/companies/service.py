from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.companies.models import CompanyProfileRecord, DocumentCacheRecord, FilingRecord, FilingSectionRecord
from app.dart import DartClient
from app.dart.parsers import extract_document_sections

# 자소서 리서치에 쓰이는 서술형 섹션만 보관한다. 재무제표 표(재무에 관한 사항)는
# 구조화된 재무 API로 따로 수집하므로 제외해 저장 용량을 줄인다.
STORED_SECTION_TERMS = ("회사의개요", "사업의내용", "경영진단")
STORED_SECTION_CHAR_LIMIT = 50_000


def _is_stored_section(title: str) -> bool:
    normalized = title.replace(" ", "")
    return any(term in normalized for term in STORED_SECTION_TERMS)


class CompanyResearchService:
    def __init__(self, session: Session, dart: DartClient | None, cache_dir: Path) -> None:
        self._session = session
        self._dart = dart
        self._cache_dir = cache_dir

    def refresh_company(self, corp_code: str) -> tuple[CompanyProfileRecord, list[FilingRecord]]:
        if self._dart is None:
            raise RuntimeError("DART 클라이언트가 필요한 작업입니다.")
        now = datetime.now(UTC)
        company = self._dart.get_company(corp_code)
        profile = CompanyProfileRecord(
            corp_code=corp_code,
            ceo_name=company.ceo_name,
            corporation_type=company.corporation_type,
            business_number=company.business_number,
            industry_code=company.industry_code,
            established_date=company.established_date,
            accounting_month=company.accounting_month,
            fetched_at=now,
        )
        self._session.merge(profile)
        filings: list[FilingRecord] = []
        for disclosure in self._dart.get_disclosures(corp_code, page_size=20):
            record = FilingRecord(
                receipt_number=disclosure.receipt_number,
                corp_code=corp_code,
                corporation_class=disclosure.corporation_class,
                report_name=disclosure.report_name,
                filer_name=disclosure.filer_name,
                receipt_date=disclosure.receipt_date,
                remarks=disclosure.remarks,
                fetched_at=now,
            )
            self._session.merge(record)
            filings.append(record)
        self._session.commit()
        return profile, filings

    def get_filings(self, corp_code: str) -> list[FilingRecord]:
        statement = select(FilingRecord).where(FilingRecord.corp_code == corp_code).order_by(FilingRecord.receipt_date.desc())
        return list(self._session.scalars(statement))

    def cache_and_extract(
        self, receipt_number: str, *, store_archive: bool = True
    ) -> tuple[DocumentCacheRecord, list[FilingSectionRecord]]:
        existing = self._session.get(DocumentCacheRecord, receipt_number)
        if existing is not None:
            sections = list(self._session.scalars(
                select(FilingSectionRecord)
                .where(FilingSectionRecord.receipt_number == receipt_number)
                .order_by(FilingSectionRecord.section_order)
            ))
            return existing, sections

        if self._dart is None:
            raise RuntimeError("DART 클라이언트가 필요한 작업입니다.")
        content = self._dart.download_document(receipt_number)
        extracted = extract_document_sections(content)
        relative_path = ""
        if store_archive:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            target = self._cache_dir / f"{receipt_number}.zip"
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(content)
            temporary.replace(target)
            relative_path = target.name
        record = DocumentCacheRecord(
            receipt_number=receipt_number,
            relative_path=relative_path,
            sha256=sha256(content).hexdigest(),
            byte_size=len(content),
            cached_at=datetime.now(UTC),
        )
        self._session.add(record)
        self._session.execute(delete(FilingSectionRecord).where(FilingSectionRecord.receipt_number == receipt_number))
        sections = [
            FilingSectionRecord(
                receipt_number=receipt_number,
                section_order=section.order,
                title=section.title,
                text=section.text[:STORED_SECTION_CHAR_LIMIT],
                source_element_id=section.source_element_id,
            )
            for section in extracted
            if _is_stored_section(section.title)
        ]
        self._session.add_all(sections)
        self._session.commit()
        return record, sections
