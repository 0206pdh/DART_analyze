from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analysis.provider import Generation
from app.analysis.schemas import AnalysisRequest, CompanyInsight, GeneratedAnalysis, RequirementConnection, WritingDirection
from app.analysis.service import AnalysisService, validate_citations
from app.companies.models import CompanyRecord, FilingRecord, FilingSectionRecord
from app.database import Base


class FakeProvider:
    model = "fake-model"

    def generate(self, payload: dict[str, object]) -> Generation:
        source_id = payload["evidence"][0]["source_id"]  # type: ignore[index]
        return Generation(result=GeneratedAnalysis(
            job_summary="백엔드 서비스 개발 역할",
            company_insights=[CompanyInsight(kind="fact", statement="클라우드 사업을 확대한다.", source_ids=[source_id])],
            connections=[RequirementConnection(requirement="API 개발", company_context="클라우드", connection="확장성 경험 강조", source_ids=[source_id])],
            writing_directions=[WritingDirection(title="확장성", core_message="성장 기여", experience_prompt="트래픽 개선 경험은?", source_ids=[source_id])],
            cautions=[],
        ), input_tokens=10, output_tokens=20)


def test_analysis_is_grounded_and_persisted_without_raw_input() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompanyRecord(corp_code="00126380", corp_name="삼성전자", normalized_name="삼성전자", stock_code="005930", modify_date="20260904"))
        session.add(FilingRecord(receipt_number="20260904000001", corp_code="00126380", corporation_class="Y", report_name="반기보고서", filer_name="삼성전자", receipt_date="20260904", fetched_at=datetime.now(UTC)))
        session.add(FilingSectionRecord(receipt_number="20260904000001", section_order=1, title="II. 사업의 내용", text="클라우드 사업 확대와 서비스 안정성 강화를 추진합니다." * 5))
        session.commit()

        request = AnalysisRequest(corp_code="00126380", role="백엔드", job_posting="API 개발과 서비스 운영 경험이 필요합니다.", experience="대규모 API를 개선했습니다.")
        response = AnalysisService(session, FakeProvider(), 40000).analyze(request)
        stored = session.get(__import__("app.companies.models", fromlist=["AnalysisRunRecord"]).AnalysisRunRecord, response.analysis_id)
        assert response.result.company_insights[0].source_ids[0].startswith("DART:")
        assert stored is not None
        assert "대규모 API" not in stored.result_json
        assert len(stored.input_hash) == 64


def test_unknown_citations_remove_grounded_claims() -> None:
    result = GeneratedAnalysis(
        job_summary="요약",
        company_insights=[CompanyInsight(kind="fact", statement="근거 없음", source_ids=["FAKE"])],
        connections=[], writing_directions=[], cautions=[],
    )
    assert validate_citations(result, {"DART:1"}).company_insights == []


def test_result_size_is_bounded() -> None:
    source_id = "DART:1"
    result = GeneratedAnalysis(
        job_summary="요" * 250,
        company_insights=[CompanyInsight(kind="fact", statement="사" * 400, source_ids=[source_id]) for _ in range(5)],
        connections=[RequirementConnection(requirement="역량", company_context="맥" * 400, connection="연" * 400, source_ids=[source_id]) for _ in range(5)],
        writing_directions=[WritingDirection(title="방향", core_message="핵" * 400, experience_prompt="질" * 400, source_ids=[source_id]) for _ in range(5)],
        cautions=["주의"] * 4,
    )
    bounded = validate_citations(result, {source_id})
    assert len(bounded.job_summary) == 200
    assert len(bounded.company_insights) == 3
    assert len(bounded.connections) == 3
    assert len(bounded.writing_directions) == 3
    assert len(bounded.cautions) == 2
    assert len(bounded.connections[0].connection) == 300
