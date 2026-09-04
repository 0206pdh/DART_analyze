from fastapi import APIRouter, Depends, HTTPException
from openai import APIError, LengthFinishReasonError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.analysis.provider import OpenAIAnalysisProvider
from app.analysis.schemas import AnalysisRequest, AnalysisResponse
from app.analysis.service import AnalysisService
from app.config import Settings
from app.companies.models import FilingRecord, FilingSectionRecord
from app.companies.service import CompanyResearchService
from app.companies.router import get_dart_client
from app.dart import DartClient
from app.database import get_session
from sqlalchemy import select


router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
def create_analysis(
    request: AnalysisRequest,
    session: Session = Depends(get_session),
    dart: DartClient = Depends(get_dart_client),
) -> AnalysisResponse:
    settings = Settings.from_env()
    if settings.openai_api_key is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    provider = OpenAIAnalysisProvider(
        settings.openai_api_key,
        settings.openai_model,
        settings.openai_max_output_tokens,
    )
    try:
        section_exists = session.scalar(
            select(FilingSectionRecord.id)
            .join(FilingRecord, FilingRecord.receipt_number == FilingSectionRecord.receipt_number)
            .where(FilingRecord.corp_code == request.corp_code)
            .limit(1)
        )
        if section_exists is None:
            research = CompanyResearchService(session, dart, settings.document_cache_dir)
            filings = research.get_filings(request.corp_code)
            if not filings:
                _, filings = research.refresh_company(request.corp_code)
            if filings:
                research.cache_and_extract(filings[0].receipt_number)
        return AnalysisService(session, provider, settings.analysis_max_source_chars).analyze(request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except APIError as error:
        raise HTTPException(status_code=502, detail="AI 분석 서비스 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.") from error
    except (LengthFinishReasonError, ValidationError) as error:
        raise HTTPException(status_code=502, detail="AI 분석 결과가 너무 길어 완성되지 않았습니다. 다시 시도해 주세요.") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
