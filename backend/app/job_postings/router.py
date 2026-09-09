from fastapi import APIRouter, File, HTTPException, UploadFile

from app.analysis.schemas import JobPostingImportResponse, JobPostingUrlRequest
from app.job_postings.service import JobPostingImportError, MAX_TEXT_CHARS, extract_text, import_from_url


router = APIRouter(prefix="/api/job-postings", tags=["job-postings"])


@router.post("/from-url", response_model=JobPostingImportResponse)
def import_job_posting_url(payload: JobPostingUrlRequest) -> JobPostingImportResponse:
    try:
        source_url, text = import_from_url(payload.url)
    except JobPostingImportError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return JobPostingImportResponse(source_url=source_url, text=text, character_count=len(text))


@router.post("/from-file", response_model=JobPostingImportResponse)
async def import_job_posting_file(file: UploadFile = File(...)) -> JobPostingImportResponse:
    filename = file.filename or ""
    try:
        content = await file.read()
        title, text = extract_text(content, filename, file.content_type)
        text = text[:MAX_TEXT_CHARS]
    except JobPostingImportError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return JobPostingImportResponse(title=title or filename, text=text, character_count=len(text))
