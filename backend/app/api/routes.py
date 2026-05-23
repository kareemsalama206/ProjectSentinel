from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.core.config import get_settings
from app.db import get_db
from app.services.analyzer import AnalysisDraft, analyze_project
from app.services.pdf_report import build_pdf_report
from app.services.safe_zip import ArchiveValidationError, safe_extract_zip, validate_upload_name


router = APIRouter()


@router.get("/health", response_model=schemas.HealthOut)
def health() -> schemas.HealthOut:
    return schemas.HealthOut(status="ok", service="ProjectSentinel")


@router.post("/analyses/upload", response_model=schemas.AnalysisSummaryOut, status_code=201)
async def upload_analysis(file: UploadFile = File(...), db: Session = Depends(get_db)) -> schemas.AnalysisSummaryOut:
    settings = get_settings()
    validate_or_400(file.filename or "")
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="Project archive is too large.")

    temp_dir = Path(tempfile.mkdtemp(prefix="projectsentinel_"))
    try:
        extract_dir = temp_dir / "project"
        safe_extract_zip(content, extract_dir)
        analysis_root = resolve_analysis_root(extract_dir)
        project_name = derive_project_name(file.filename or "project.zip", analysis_root)
        draft = analyze_project(analysis_root, project_name)
        analysis = persist_analysis(db, draft, file.filename or "project.zip")
        return to_summary(analysis)
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/analyses", response_model=list[schemas.AnalysisSummaryOut])
def list_analyses(db: Session = Depends(get_db)) -> list[schemas.AnalysisSummaryOut]:
    analyses = db.scalars(
        select(models.Analysis)
        .options(selectinload(models.Analysis.technologies), selectinload(models.Analysis.findings), selectinload(models.Analysis.file_summary))
        .order_by(models.Analysis.created_at.desc())
        .limit(25)
    ).all()
    return [to_summary(analysis) for analysis in analyses]


@router.get("/analyses/{analysis_id}", response_model=schemas.AnalysisDetailOut)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> schemas.AnalysisDetailOut:
    analysis = get_analysis_or_404(db, analysis_id)
    return to_detail(analysis)


@router.get("/analyses/{analysis_id}/findings", response_model=list[schemas.FindingOut])
def get_findings(analysis_id: int, db: Session = Depends(get_db)) -> list[schemas.FindingOut]:
    analysis = get_analysis_or_404(db, analysis_id)
    return [schemas.FindingOut.model_validate(finding) for finding in analysis.findings]


@router.get("/analyses/{analysis_id}/report")
def get_report(analysis_id: int, db: Session = Depends(get_db)) -> Response:
    analysis = get_analysis_or_404(db, analysis_id)
    pdf = build_pdf_report(analysis)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="projectsentinel-analysis-{analysis.id}.pdf"'},
    )


# Keep this static route before /analyses/{analysis_id}; FastAPI matches routes in
# registration order, and "reset" must not be treated as the dynamic analysis_id.
@router.delete("/analyses/reset", response_model=schemas.ResetAnalysesOut)
def reset_analyses(db: Session = Depends(get_db)) -> schemas.ResetAnalysesOut:
    analyses = db.scalars(select(models.Analysis)).all()
    deleted_count = len(analyses)
    for analysis in analyses:
        db.delete(analysis)
    db.commit()
    return schemas.ResetAnalysesOut(deleted_count=deleted_count)


@router.delete("/analyses/{analysis_id}", response_model=schemas.DeleteAnalysisOut)
def delete_analysis(analysis_id: int, db: Session = Depends(get_db)) -> schemas.DeleteAnalysisOut:
    analysis = get_analysis_or_404(db, analysis_id)
    db.delete(analysis)
    db.commit()
    return schemas.DeleteAnalysisOut(deleted=True, analysis_id=analysis_id)


def validate_or_400(file_name: str) -> None:
    try:
        validate_upload_name(file_name)
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def resolve_analysis_root(extract_dir: Path) -> Path:
    children = list(extract_dir.iterdir())
    directories = [path for path in children if path.is_dir()]
    files = [path for path in children if path.is_file()]
    if len(directories) == 1 and not files:
        return directories[0]
    return extract_dir


def derive_project_name(file_name: str, analysis_root: Path) -> str:
    if analysis_root.name != "project":
        return analysis_root.name
    return Path(file_name).stem or "Uploaded project"


def persist_analysis(db: Session, draft: AnalysisDraft, file_name: str) -> models.Analysis:
    analysis = models.Analysis(
        project_name=draft.project_name,
        file_name=file_name,
        project_type=draft.project_type,
        overall_score=draft.scores["overall_score"],
        security_score=draft.scores["security_score"],
        documentation_score=draft.scores["documentation_score"],
        testing_score=draft.scores["testing_score"],
        docker_score=draft.scores["docker_score"],
        github_score=draft.scores["github_score"],
        deployment_score=draft.scores["deployment_score"],
        maintainability_score=draft.scores["maintainability_score"],
    )
    analysis.technologies = [
        models.DetectedTechnology(
            name=technology.name,
            category=technology.category,
            evidence_file=technology.evidence_file,
            reason=technology.reason,
            confidence=technology.confidence,
        )
        for technology in draft.technologies
    ]
    analysis.findings = [
        models.Finding(
            category=finding.category,
            severity=finding.severity,
            priority=finding.priority,
            title=finding.title,
            description=finding.description,
            why_it_matters=finding.why_it_matters,
            recommendation=finding.recommendation,
            file_path=finding.file_path,
            line_number=finding.line_number,
        )
        for finding in draft.findings
    ]
    analysis.file_summary = models.FileSummary(
        total_files=draft.file_summary.total_files,
        scanned_files=draft.file_summary.scanned_files,
        skipped_files=draft.file_summary.skipped_files,
        total_size_bytes=draft.file_summary.total_size_bytes,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return get_analysis_or_404(db, analysis.id)


def get_analysis_or_404(db: Session, analysis_id: int) -> models.Analysis:
    analysis = db.scalar(
        select(models.Analysis)
        .where(models.Analysis.id == analysis_id)
        .options(selectinload(models.Analysis.technologies), selectinload(models.Analysis.findings), selectinload(models.Analysis.file_summary))
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


def to_summary(analysis: models.Analysis) -> schemas.AnalysisSummaryOut:
    return schemas.AnalysisSummaryOut(
        id=analysis.id,
        project_name=analysis.project_name,
        file_name=analysis.file_name,
        project_type=analysis.project_type,
        overall_score=analysis.overall_score,
        security_score=analysis.security_score,
        documentation_score=analysis.documentation_score,
        testing_score=analysis.testing_score,
        docker_score=analysis.docker_score,
        github_score=analysis.github_score,
        deployment_score=analysis.deployment_score,
        maintainability_score=analysis.maintainability_score,
        created_at=analysis.created_at,
        technologies=[schemas.DetectedTechnologyOut.model_validate(tech) for tech in analysis.technologies],
        severity_counts=severity_counts(analysis),
        score_explanations=score_explanations(analysis),
        file_summary=schemas.FileSummaryOut.model_validate(analysis.file_summary) if analysis.file_summary else None,
    )


def to_detail(analysis: models.Analysis) -> schemas.AnalysisDetailOut:
    summary = to_summary(analysis)
    return schemas.AnalysisDetailOut(
        **summary.model_dump(),
        findings=[schemas.FindingOut.model_validate(finding) for finding in analysis.findings],
    )


def severity_counts(analysis: models.Analysis) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0, "passed": 0}
    for finding in analysis.findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def score_explanations(analysis: models.Analysis) -> schemas.ScoreExplanations:
    # Reconstruct explanations from persisted findings instead of storing them.
    # Old analyses may reflect current scoring rules if calculate_scores changes.
    from app.services.analyzer import calculate_scores

    finding_drafts = [
        type(
            "FindingView",
            (),
            {"category": f.category, "severity": f.severity, "title": f.title},
        )()
        for f in analysis.findings
    ]
    tech_drafts = [type("TechView", (), {"name": t.name, "category": t.category})() for t in analysis.technologies]
    scores, explanations = calculate_scores(finding_drafts, set(), tech_drafts, analysis.project_type)
    _ = scores
    return schemas.ScoreExplanations(**explanations)
