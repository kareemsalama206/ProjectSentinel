from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(120), nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    security_score: Mapped[int] = mapped_column(Integer, nullable=False)
    documentation_score: Mapped[int] = mapped_column(Integer, nullable=False)
    testing_score: Mapped[int] = mapped_column(Integer, nullable=False)
    docker_score: Mapped[int] = mapped_column(Integer, nullable=False)
    github_score: Mapped[int] = mapped_column(Integer, nullable=False)
    deployment_score: Mapped[int] = mapped_column(Integer, nullable=False)
    maintainability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    technologies: Mapped[list["DetectedTechnology"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    file_summary: Mapped["FileSummary"] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", uselist=False
    )


class DetectedTechnology(Base):
    __tablename__ = "detected_technologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_file: Mapped[str] = mapped_column(String(500), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="technologies")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis: Mapped[Analysis] = relationship(back_populates="findings")


class FileSummary(Base):
    __tablename__ = "file_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), nullable=False, unique=True)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    scanned_files: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_files: Mapped[int] = mapped_column(Integer, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    analysis: Mapped[Analysis] = relationship(back_populates="file_summary")
