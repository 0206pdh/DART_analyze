from fastapi import APIRouter, Depends, HTTPException
from openai import APIError, APITimeoutError, LengthFinishReasonError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.analysis.provider import OpenAIAnalysisProvider
from app.analysis.schemas import AnalysisRequest, AnalysisResponse, DraftRequest, DraftResponse
from app.analysis.service import AnalysisService
from app.config import Settings
from app.companies.models import FilingRecord, FilingSectionRecord
from app.companies.service import CompanyResearchService
from app.companies.router import get_dart_client
from app.dart import DartClient
from app.database import get_session
from app.security import enforce_api_protection
from sqlalchemy import select


router = APIRouter(prefix="/api/analyses", tags=["analyses"], dependencies=[Depends(enforce_api_protection)])


@router.post("", response_model=AnalysisResponse)
def create_analysis(
    request: AnalysisRequest,
    session: Session = Depends(get_session),
    dart: DartClient | None = Depends(get_dart_client),
) -> AnalysisResponse:
    settings = Settings.from_env()
    if settings.openai_api_key is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    provider = OpenAIAnalysisProvider(
        settings.openai_api_key,
        settings.openai_model,
        settings.openai_max_output_tokens,
        settings.openai_timeout_seconds,
    )
    try:
        section_exists = session.scalar(
            select(FilingSectionRecord.id)
            .join(FilingRecord, FilingRecord.receipt_number == FilingSectionRecord.receipt_number)
            .where(FilingRecord.corp_code == request.corp_code)
            .limit(1)
        )
        if section_exists is None:
            if settings.read_only:
                raise HTTPException(
                    status_code=409,
                    detail="아직 분석 데이터가 준비되지 않은 기업입니다. 현재는 주요 상장사만 지원합니다.",
                )
            research = CompanyResearchService(session, dart, settings.document_cache_dir)
            filings = research.get_filings(request.corp_code)
            if not filings:
                _, filings = research.refresh_company(request.corp_code)
            if filings:
                research.cache_and_extract(filings[0].receipt_number)
        return AnalysisService(session, provider, settings.analysis_max_source_chars).analyze(request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="AI 분석이 35초 안에 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.") from error
    except APIError as error:
        raise HTTPException(status_code=502, detail="AI 분석 서비스 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.") from error
    except (LengthFinishReasonError, ValidationError) as error:
        raise HTTPException(status_code=502, detail="AI 분석 결과가 너무 길어 완성되지 않았습니다. 다시 시도해 주세요.") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/draft", response_model=DraftResponse)
def create_draft(
    request: DraftRequest,
    session: Session = Depends(get_session),
) -> DraftResponse:
    settings = Settings.from_env()
    if settings.openai_api_key is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    provider = OpenAIAnalysisProvider(
        settings.openai_api_key,
        settings.openai_model,
        settings.openai_max_output_tokens,
        settings.openai_timeout_seconds,
    )
    try:
        service = AnalysisService(session, provider, settings.analysis_max_source_chars)
        context = service.build_context(request.corp_code)
        if not context.sources:
            raise RuntimeError("초안을 만들 공시 근거가 없습니다.")
        generated = provider.generate_draft({
            "company": context.company.corp_name,
            "role": request.role,
            "job_posting": request.job_posting,
            "applicant_experience": request.experience,
            "writing_direction": {
                "title": request.direction_title,
                "core_message": request.direction_message,
                "experience_prompt": request.experience_prompt,
            },
            "evidence": [source.model_dump() for source in context.sources],
        })
        allowed = {source.source_id for source in context.sources}
        generated.source_ids = [source_id for source_id in generated.source_ids if source_id in allowed]
        generated.draft = generated.draft[:1500]
        generated.feedback = generated.feedback[:500]
        return DraftResponse(
            company_name=context.company.corp_name,
            role=request.role,
            draft=generated.draft,
            feedback=generated.feedback,
            source_ids=generated.source_ids,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="자기소개서 초안이 35초 안에 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.") from error
    except APIError as error:
        raise HTTPException(status_code=502, detail="자기소개서 초안 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.") from error
    except (LengthFinishReasonError, ValidationError) as error:
        raise HTTPException(status_code=502, detail="초안이 길이 제한으로 완성되지 않았습니다. 다시 시도해 주세요.") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
