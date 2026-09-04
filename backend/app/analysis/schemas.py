from typing import Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    corp_code: str = Field(pattern=r"^\d{8}$")
    role: str = Field(min_length=1, max_length=200)
    job_posting: str = Field(min_length=20, max_length=20000)
    experience: str | None = Field(default=None, max_length=10000)


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


class GeneratedAnalysis(BaseModel):
    job_summary: str
    company_insights: list[CompanyInsight]
    connections: list[RequirementConnection]
    writing_directions: list[WritingDirection]
    cautions: list[str]


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
