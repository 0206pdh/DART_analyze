import hashlib
import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.provider import AnalysisProvider
from app.analysis.schemas import AnalysisRequest, AnalysisResponse, EvidenceSource, GeneratedAnalysis
from app.companies.models import AnalysisRunRecord, CompanyRecord, FilingRecord, FilingSectionRecord, FinancialMetricRecord


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    company: CompanyRecord
    sources: list[EvidenceSource]


class AnalysisService:
    def __init__(self, session: Session, provider: AnalysisProvider, max_source_chars: int) -> None:
        self._session = session
        self._provider = provider
        self._max_source_chars = max_source_chars

    def build_context(self, corp_code: str) -> AnalysisContext:
        company = self._session.get(CompanyRecord, corp_code)
        if company is None:
            raise LookupError("회사를 찾을 수 없습니다.")

        sections = list(self._session.execute(
            select(FilingSectionRecord, FilingRecord)
            .join(FilingRecord, FilingRecord.receipt_number == FilingSectionRecord.receipt_number)
            .where(FilingRecord.corp_code == corp_code)
            .order_by(FilingRecord.receipt_date.desc(), FilingSectionRecord.section_order)
        ).all())
        ranked = sorted(sections, key=lambda row: (_section_priority(row[0].title), -int(row[1].receipt_date)))
        sources: list[EvidenceSource] = []
        remaining = self._max_source_chars
        seen_receipts: set[str] = set()
        for section, filing in ranked:
            if remaining <= 0 or len(seen_receipts) >= 3:
                break
            excerpt = _clean_text(section.text)[: min(12000, remaining)]
            if len(excerpt) < 80:
                continue
            source_id = f"DART:{filing.receipt_number}:{section.section_order}"
            sources.append(EvidenceSource(
                source_id=source_id,
                source_type="filing",
                title=section.title,
                report_name=filing.report_name,
                receipt_number=filing.receipt_number,
                viewer_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing.receipt_number}",
                excerpt=excerpt,
            ))
            remaining -= len(excerpt)
            seen_receipts.add(filing.receipt_number)

        metrics = list(self._session.scalars(
            select(FinancialMetricRecord)
            .where(FinancialMetricRecord.corp_code == corp_code)
            .order_by(FinancialMetricRecord.business_year.desc(), FinancialMetricRecord.report_code.desc())
            .limit(12)
        ))
        for metric in metrics:
            comparison = "비교값 없음"
            if metric.previous_amount not in {None, 0}:
                change = (metric.current_amount - metric.previous_amount) / abs(metric.previous_amount) * 100
                comparison = f"비교 기준 대비 {change:+.1f}%"
            sources.append(EvidenceSource(
                source_id=f"FIN:{metric.business_year}:{metric.report_code}:{metric.metric_code}",
                source_type="financial",
                title=metric.account_name,
                excerpt=f"{metric.business_year} {metric.comparison_basis}: {metric.current_amount:,} {metric.currency or '원'}, {comparison}",
            ))
        return AnalysisContext(company=company, sources=sources)

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        context = self.build_context(request.corp_code)
        if not context.sources:
            raise RuntimeError("분석할 공시 근거가 없습니다. 먼저 기업 공시와 원문을 수집해 주세요.")
        payload = {
            "company": context.company.corp_name,
            "role": request.role,
            "job_posting": request.job_posting,
            "applicant_experience": request.experience or "입력 없음",
            "evidence": [source.model_dump() for source in context.sources],
        }
        generation = self._provider.generate(payload)
        result = validate_citations(generation.result, {source.source_id for source in context.sources})
        analysis_id = str(uuid4())
        digest = hashlib.sha256(
            f"{request.corp_code}\0{request.role}\0{request.job_posting}\0{request.experience or ''}".encode()
        ).hexdigest()
        self._session.add(AnalysisRunRecord(
            id=analysis_id,
            corp_code=request.corp_code,
            role=request.role,
            input_hash=digest,
            model=self._provider.model,
            result_json=result.model_dump_json(),
            sources_json=json.dumps([source.model_dump() for source in context.sources], ensure_ascii=False),
            input_tokens=generation.input_tokens,
            output_tokens=generation.output_tokens,
        ))
        self._session.commit()
        return AnalysisResponse(
            analysis_id=analysis_id,
            company_name=context.company.corp_name,
            role=request.role,
            model=self._provider.model,
            result=result,
            sources=context.sources,
            disclaimer="공시 기반 참고 분석이며 회사의 공식 채용 기준이나 합격을 보장하지 않습니다.",
        )


def validate_citations(result: GeneratedAnalysis, allowed: set[str]) -> GeneratedAnalysis:
    result.job_summary = result.job_summary[:200]
    for insight in result.company_insights:
        insight.statement = insight.statement[:300]
        insight.source_ids = [source_id for source_id in insight.source_ids if source_id in allowed]
    result.company_insights = [item for item in result.company_insights if item.source_ids][:3]
    for focus in result.investment_focus:
        focus.area = focus.area[:40]
        focus.detail = focus.detail[:200]
        focus.source_ids = [source_id for source_id in focus.source_ids if source_id in allowed]
    result.investment_focus = [item for item in result.investment_focus if item.source_ids][:2]
    for connection in result.connections:
        connection.company_context = connection.company_context[:300]
        connection.connection = connection.connection[:300]
        connection.source_ids = [source_id for source_id in connection.source_ids if source_id in allowed]
    result.connections = [item for item in result.connections if item.source_ids][:3]
    for direction in result.writing_directions:
        direction.core_message = direction.core_message[:300]
        direction.experience_prompt = direction.experience_prompt[:300]
        direction.source_ids = [source_id for source_id in direction.source_ids if source_id in allowed]
    result.writing_directions = result.writing_directions[:3]
    result.cautions = result.cautions[:2]
    return result


def _section_priority(title: str) -> int:
    normalized = title.replace(" ", "")
    terms = ("사업의내용", "경영진단", "위험", "연구개발", "회사의개요")
    return next((index for index, term in enumerate(terms) if term in normalized), len(terms))


def _clean_text(value: str) -> str:
    return " ".join(value.split())
