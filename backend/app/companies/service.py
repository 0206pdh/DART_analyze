from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.companies.models import CompanyProfileRecord, DocumentCacheRecord, FilingRecord, FilingSectionRecord
from app.dart import DartClient
from app.dart.parsers import extract_document_sections


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

    def cache_and_extract(self, receipt_number: str) -> tuple[DocumentCacheRecord, list[FilingSectionRecord]]:
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
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        target = self._cache_dir / f"{receipt_number}.zip"
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        record = DocumentCacheRecord(
            receipt_number=receipt_number,
            relative_path=target.name,
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
                text=section.text,
                source_element_id=section.source_element_id,
            )
            for section in extracted
        ]
        self._session.add_all(sections)
        self._session.commit()
        return record, sections
