from typing import Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    corp_code: str = Field(pattern=r"^\d{8}$")
    role: str = Field(min_length=1, max_length=200)
    job_posting: str = Field(min_length=20, max_length=20000)
    experience: str | None = Field(default=None, max_length=10000)


class DraftRequest(BaseModel):
    corp_code: str = Field(pattern=r"^\d{8}$")
    role: str = Field(min_length=1, max_length=200)
    job_posting: str = Field(min_length=20, max_length=20000)
    experience: str = Field(min_length=20, max_length=10000)
    direction_title: str = Field(min_length=1, max_length=200)
    direction_message: str = Field(min_length=1, max_length=500)
    experience_prompt: str = Field(min_length=1, max_length=500)


class CompanyInsight(BaseModel):
    kind: Literal["fact", "inference"]
    statement: str
    source_ids: list[str]


class RequirementConnection(BaseModel):
    requirement: str
    company_context: str
    connection: str
    source_ids: list[str]


class WritingDirection(BaseModel):
    title: str
    core_message: str
    experience_prompt: str
    source_ids: list[str]


class InvestmentFocus(BaseModel):
    kind: Literal["fact", "inference"]
    area: str
    detail: str
    source_ids: list[str]


class GeneratedAnalysis(BaseModel):
    job_summary: str
    company_insights: list[CompanyInsight]
    investment_focus: list[InvestmentFocus]
    connections: list[RequirementConnection]
    writing_directions: list[WritingDirection]
    cautions: list[str]


class GeneratedDraft(BaseModel):
    draft: str
    feedback: str
    source_ids: list[str]


class EvidenceSource(BaseModel):
    source_id: str
    source_type: Literal["filing", "financial"]
    title: str
    report_name: str | None = None
    receipt_number: str | None = None
    viewer_url: str | None = None
    excerpt: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    company_name: str
    role: str
    model: str
    result: GeneratedAnalysis
    sources: list[EvidenceSource]
    disclaimer: str
    cached: bool = False


class DraftResponse(BaseModel):
    company_name: str
    role: str
    draft: str
    feedback: str
    source_ids: list[str]


class JobPostingImportResponse(BaseModel):
    source_url: str | None = None
    title: str | None = None
    text: str
    character_count: int


class JobPostingUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
