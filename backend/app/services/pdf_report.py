from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Analysis
from app.services.analyzer import calculate_scores, score_status


def build_pdf_report(analysis: Analysis) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "SentinelTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "SentinelHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=14,
        spaceAfter=8,
    )
    body = ParagraphStyle("SentinelBody", parent=styles["BodyText"], fontSize=9.5, leading=13)

    elements = [
        Paragraph("ProjectSentinel Audit Report", title),
        Paragraph(f"<b>Project:</b> {escape(analysis.project_name)}", body),
        Paragraph(f"<b>Project type:</b> {escape(analysis.project_type)}", body),
        Paragraph(f"<b>Analysis date:</b> {analysis.created_at.strftime('%Y-%m-%d %H:%M UTC')}", body),
        Spacer(1, 10),
    ]

    explanations = score_explanations_for_pdf(analysis)
    severity_counts = {"critical": 0, "warning": 0, "info": 0, "passed": 0}
    for finding in analysis.findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

    elements.append(Paragraph("Executive Summary", heading))
    elements.append(
        two_col_table(
            [
                ["Overall Score", f"{analysis.overall_score} / 100"],
                ["Risk Level", score_status(analysis.overall_score)],
                ["Total Findings", len(analysis.findings)],
                ["Critical Findings", severity_counts["critical"]],
                ["Warnings", severity_counts["warning"]],
                ["Passed Checks", severity_counts["passed"]],
            ]
        )
    )

    score_rows = [
        ["Score", "Value", "Status"],
        ["Security", analysis.security_score, explanations["security"]["status"]],
        ["Documentation", analysis.documentation_score, explanations["documentation"]["status"]],
        ["Testing", analysis.testing_score, explanations["testing"]["status"]],
        ["Docker", analysis.docker_score, explanations["docker"]["status"]],
        ["GitHub Readiness", analysis.github_score, explanations["github"]["status"]],
        ["Deployment Readiness", analysis.deployment_score, explanations["deployment"]["status"]],
        ["Maintainability", analysis.maintainability_score, explanations["maintainability"]["status"]],
    ]
    elements.append(Paragraph("Score Breakdown", heading))
    elements.append(table_with_header(score_rows, [2.1 * inch, 1.0 * inch, 1.3 * inch]))
    elements.append(Paragraph("Score Explanations", heading))
    for label in ["security", "documentation", "testing", "docker", "github", "deployment", "maintainability"]:
        explanation = explanations[label]
        elements.append(Paragraph(f"<b>{label.title()}:</b> {escape(explanation['explanation'])}", body))
        if explanation["deductions"]:
            elements.append(Paragraph(f"<b>Deductions:</b> {escape('; '.join(explanation['deductions'][:4]))}", body))
        if explanation["positives"]:
            elements.append(Paragraph(f"<b>Positives:</b> {escape('; '.join(explanation['positives'][:4]))}", body))
        elements.append(Paragraph(f"<b>Fix next:</b> {escape(explanation['recommendation'])}", body))
        elements.append(Spacer(1, 3))

    elements.append(Paragraph("Top Priority Fixes", heading))
    priority_findings = sorted(
        [finding for finding in analysis.findings if finding.severity in {"critical", "warning"}],
        key=lambda finding: (priority_rank(finding.priority), severity_rank(finding.severity), finding.title),
    )[:5]
    if not priority_findings:
        elements.append(Paragraph("No critical or warning findings were generated.", body))
    for finding in priority_findings:
        elements.append(Paragraph(f"<b>{escape(finding.priority or 'P3')} {escape(finding.severity.title())} - {escape(finding.title)}</b>", body))
        elements.append(Paragraph(f"<b>Why it matters:</b> {escape(finding.why_it_matters or finding.description)}", body))
        elements.append(Paragraph(f"<b>Recommendation:</b> {escape(finding.recommendation)}", body))
        elements.append(Spacer(1, 5))

    elements.append(Paragraph("Detected Technologies", heading))
    if analysis.technologies:
        tech_rows = [["Technology", "Category", "Evidence", "Confidence"]]
        for tech in analysis.technologies:
            tech_rows.append(
                [
                    escape(tech.name),
                    escape(tech.category),
                    escape(tech.evidence_file or "Not available"),
                    escape(tech.confidence or "not checked"),
                ]
            )
        elements.append(table_with_header(tech_rows, [1.35 * inch, 1.0 * inch, 2.2 * inch, 0.9 * inch]))
        for tech in analysis.technologies[:12]:
            elements.append(Paragraph(f"<b>{escape(tech.name)}:</b> {escape(tech.reason or 'Detected from project indicators.')}", body))
    else:
        elements.append(Paragraph("No common technologies detected.", body))

    elements.append(Paragraph("Severity Summary", heading))
    elements.append(two_col_table([[key.title(), value] for key, value in severity_counts.items()]))

    add_finding_section(elements, "Critical Findings", analysis.findings, "critical", heading, body)
    add_finding_section(elements, "Warnings", analysis.findings, "warning", heading, body)
    add_passed_summary(elements, analysis.findings, heading, body)

    elements.append(Paragraph("Recommendations", heading))
    recommendations = [finding for finding in analysis.findings if finding.severity in {"critical", "warning"}][:12]
    if not recommendations:
        elements.append(Paragraph("No critical or warning recommendations were generated by the MVP scanner.", body))
    for finding in recommendations:
        elements.append(Paragraph(f"[ ] <b>{escape(finding.priority or 'P3')} {escape(finding.title)}:</b> {escape(finding.recommendation)}", body))
        elements.append(Spacer(1, 4))

    elements.append(Paragraph("GitHub Readiness Summary", heading))
    add_category_summary(elements, analysis.findings, "github", body)
    elements.append(Paragraph("Deployment Readiness Summary", heading))
    add_category_summary(elements, analysis.findings, "docker", body)

    doc.build(elements)
    return buffer.getvalue()


def add_finding_section(elements, title: str, findings, severity: str, heading, body) -> None:
    elements.append(Paragraph(title, heading))
    selected = [finding for finding in findings if finding.severity == severity][:15]
    if not selected:
        elements.append(Paragraph(f"No {severity} findings.", body))
        return
    for finding in selected:
        location = f" ({escape(finding.file_path)}" + (f":{finding.line_number}" if finding.line_number else "") + ")" if finding.file_path else ""
        elements.append(Paragraph(f"<b>{escape(finding.priority or 'P3')} - {escape(finding.title)}</b>{location}", body))
        elements.append(Paragraph(escape(finding.description), body))
        if finding.why_it_matters:
            elements.append(Paragraph(f"<b>Why it matters:</b> {escape(finding.why_it_matters)}", body))
        elements.append(Spacer(1, 5))


def add_category_summary(elements, findings, category: str, body) -> None:
    selected = [finding for finding in findings if finding.category == category and finding.severity in {"critical", "warning", "passed"}]
    if not selected:
        elements.append(Paragraph("No checks were available for this category.", body))
        return
    for finding in selected[:8]:
        elements.append(Paragraph(f"<b>{escape(finding.severity.title())}:</b> {escape(finding.title)}", body))


def add_passed_summary(elements, findings, heading, body) -> None:
    passed = [finding for finding in findings if finding.severity == "passed"]
    elements.append(Paragraph("Passed Checks Summary", heading))
    if not passed:
        elements.append(Paragraph("No passed checks were recorded.", body))
        return
    categories: dict[str, int] = {}
    for finding in passed:
        categories[finding.category] = categories.get(finding.category, 0) + 1
    elements.append(two_col_table([[category.title(), count] for category, count in sorted(categories.items())]))


def priority_rank(priority: str | None) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority or "P3", 3)


def severity_rank(severity: str) -> int:
    return {"critical": 0, "warning": 1, "info": 2, "passed": 3}.get(severity, 4)


def two_col_table(rows: list[list[object]]) -> Table:
    table = Table(rows, colWidths=[2.4 * inch, 1.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def table_with_header(rows: list[list[object]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ede9fe")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fafafa")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d4d4d8")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#18181b")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def score_explanations_for_pdf(analysis: Analysis) -> dict:
    finding_views = [
        type("FindingView", (), {"category": finding.category, "severity": finding.severity, "title": finding.title})()
        for finding in analysis.findings
    ]
    tech_views = [
        type("TechView", (), {"name": tech.name, "category": tech.category})()
        for tech in analysis.technologies
    ]
    _, explanations = calculate_scores(finding_views, set(), tech_views, analysis.project_type)
    return explanations


def escape(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
