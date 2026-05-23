from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DetectedTechnologyOut(BaseModel):
    id: int
    name: str
    category: str
    evidence_file: str | None = None
    reason: str | None = None
    confidence: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FindingOut(BaseModel):
    id: int
    category: str
    severity: str
    priority: str | None = None
    title: str
    description: str
    why_it_matters: str | None = None
    recommendation: str
    file_path: str | None = None
    line_number: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileSummaryOut(BaseModel):
    total_files: int
    scanned_files: int
    skipped_files: int
    total_size_bytes: int

    model_config = ConfigDict(from_attributes=True)


class ScoreExplanation(BaseModel):
    status: str
    explanation: str
    positives: list[str] = []
    deductions: list[str] = []
    recommendation: str


class ScoreExplanations(BaseModel):
    overall: ScoreExplanation
    security: ScoreExplanation
    documentation: ScoreExplanation
    testing: ScoreExplanation
    docker: ScoreExplanation
    github: ScoreExplanation
    deployment: ScoreExplanation
    maintainability: ScoreExplanation


class AnalysisBaseOut(BaseModel):
    id: int
    project_name: str
    file_name: str
    project_type: str
    overall_score: int
    security_score: int
    documentation_score: int
    testing_score: int
    docker_score: int
    github_score: int
    deployment_score: int
    maintainability_score: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisSummaryOut(AnalysisBaseOut):
    technologies: list[DetectedTechnologyOut] = []
    severity_counts: dict[str, int] = {}
    score_explanations: ScoreExplanations
    file_summary: FileSummaryOut | None = None


class AnalysisDetailOut(AnalysisSummaryOut):
    findings: list[FindingOut] = []


class HealthOut(BaseModel):
    status: str
    service: str


class DeleteAnalysisOut(BaseModel):
    deleted: bool
    analysis_id: int


class ResetAnalysesOut(BaseModel):
    deleted_count: int
