import io
import zipfile
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.companies.models import CompanyRecord, FilingRecord
from app.companies.service import STORED_SECTION_CHAR_LIMIT, CompanyResearchService, _is_stored_section
from app.database import Base, create_database_engine


def _document_zip() -> bytes:
    xml = (
        "<DOCUMENT>"
        "<SECTION-1><TITLE>I. 회사의 개요</TITLE><P>회사의 개요 본문입니다. 충분히 긴 문장을 넣습니다.</P></SECTION-1>"
        "<SECTION-1><TITLE>II. 사업의 내용</TITLE><P>" + ("가" * 70000) + "</P></SECTION-1>"
        "<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE><P>재무제표 표가 담기는 매우 긴 본문 텍스트입니다.</P></SECTION-1>"
        "</DOCUMENT>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("00000000000001.xml", xml.encode("utf-8"))
    return buffer.getvalue()


class FakeDartClient:
    def download_document(self, receipt_number: str) -> bytes:
        return _document_zip()


def test_is_stored_section_keeps_narrative_drops_financial_tables() -> None:
    assert _is_stored_section("II. 사업의 내용")
    assert _is_stored_section("1. 회사의 개요")
    assert _is_stored_section("IV. 이사의 경영진단 및 분석의견")
    assert not _is_stored_section("III. 재무에 관한 사항")
    assert not _is_stored_section("VIII. 임원 및 직원 등에 관한 사항")


def test_cache_and_extract_stores_only_trimmed_narrative_sections(tmp_path) -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompanyRecord(corp_code="00126380", corp_name="삼성전자", normalized_name="삼성전자", corp_eng_name=None, normalized_eng_name=None, stock_code="005930", modify_date="20260101"))
        session.add(FilingRecord(receipt_number="00000000000001", corp_code="00126380", corporation_class="Y", report_name="반기보고서", filer_name="삼성전자", receipt_date="20260814", fetched_at=datetime.now(UTC)))
        session.commit()

        service = CompanyResearchService(session, FakeDartClient(), tmp_path)  # type: ignore[arg-type]
        record, sections = service.cache_and_extract("00000000000001", store_archive=False)

        titles = [section.title for section in sections]
        assert any("사업의 내용" in title for title in titles)
        assert any("회사의 개요" in title for title in titles)
        assert not any("재무에 관한 사항" in title for title in titles)
        longest = max(len(section.text) for section in sections)
        assert longest <= STORED_SECTION_CHAR_LIMIT
        assert record.relative_path == ""
        assert not list(tmp_path.iterdir())
