import { Download, RefreshCw } from "lucide-react";
import { formatBytes, reportUrl } from "../lib";
import { ScoreCard } from "../components/ScoreCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { TechnologyBadge } from "../components/TechnologyBadge";
import type { AnalysisDetail } from "../types/api";

interface DashboardProps {
  analysis: AnalysisDetail;
  onRefresh: () => void;
}

export function Dashboard({ analysis, onRefresh }: DashboardProps) {
  const topPriorityFixes = [...analysis.findings]
    .filter((finding) => finding.severity === "critical" || finding.severity === "warning")
    .sort(prioritySort)
    .slice(0, 5);
  const totalFindings = analysis.findings.length;
  const riskLevel = analysis.score_explanations.overall.status;

  return (
    <div className="min-w-0 space-y-6">
      <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-sentinel">
        <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-wide text-violet-700">Executive Summary</p>
            <p className="text-sm text-zinc-500">Analysis #{analysis.id}</p>
            <h2 className="mt-1 break-words text-2xl font-semibold text-zinc-950">{analysis.project_name}</h2>
            <p className="mt-2 text-sm text-zinc-600">{analysis.project_type}</p>
          </div>
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
            <button className="btn-secondary" type="button" onClick={onRefresh}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <a className="btn-primary" href={reportUrl(analysis.id)} target="_blank" rel="noreferrer">
              <Download className="h-4 w-4" />
              Export PDF Report
            </a>
          </div>
        </div>
        <div className="mt-5 grid min-w-0 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Metric label="Overall score" value={analysis.overall_score.toString()} tone="text-violet-700" />
          <Metric label="Risk level" value={riskLevel} tone={riskTone(riskLevel)} />
          <Metric label="Total findings" value={totalFindings.toString()} />
          <Metric label="Critical" value={(analysis.severity_counts.critical ?? 0).toString()} tone="text-rose-700" />
          <Metric label="Warnings" value={(analysis.severity_counts.warning ?? 0).toString()} tone="text-amber-700" />
          <Metric label="Passed checks" value={(analysis.severity_counts.passed ?? 0).toString()} tone="text-emerald-700" />
        </div>
      </section>

      <section className="min-w-0">
        <div className="mb-3">
          <h3 className="text-lg font-semibold text-zinc-950">Score Breakdown</h3>
          <p className="mt-1 text-sm text-zinc-500">Each score shows status, progress, positives, deductions, and the next recommended fix.</p>
        </div>
        <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ScoreCard label="Security" score={analysis.security_score} explanation={analysis.score_explanations.security} />
          <ScoreCard label="Documentation" score={analysis.documentation_score} explanation={analysis.score_explanations.documentation} />
          <ScoreCard label="Testing" score={analysis.testing_score} explanation={analysis.score_explanations.testing} />
          <ScoreCard label="Docker" score={analysis.docker_score} explanation={analysis.score_explanations.docker} />
          <ScoreCard label="GitHub" score={analysis.github_score} explanation={analysis.score_explanations.github} />
          <ScoreCard label="Deployment" score={analysis.deployment_score} explanation={analysis.score_explanations.deployment} />
          <ScoreCard label="Maintainability" score={analysis.maintainability_score} explanation={analysis.score_explanations.maintainability} />
        </div>
      </section>

      <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-sentinel">
        <h3 className="text-lg font-semibold text-zinc-950">Top Priority Fixes</h3>
        <p className="mt-1 text-sm text-zinc-500">Ordered by urgency: critical security issues, deployment risks, missing tests, and documentation gaps first.</p>
        <div className="mt-4 space-y-3">
          {topPriorityFixes.length ? (
            topPriorityFixes.map((finding) => (
              <div key={finding.id} className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 p-4">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs font-semibold text-zinc-700">{finding.priority ?? "P3"}</span>
                  <SeverityBadge severity={finding.severity} />
                  <p className="min-w-0 break-words font-medium text-zinc-950">{finding.title}</p>
                </div>
                <p className="mt-2 break-words text-sm leading-6 text-zinc-600">{finding.why_it_matters}</p>
                <p className="mt-1 text-sm leading-6 text-zinc-600">
                  <span className="font-medium text-zinc-900">Recommendation:</span> <span className="break-words">{finding.recommendation}</span>
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-zinc-500">No critical or warning findings were generated.</p>
          )}
        </div>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-sentinel">
          <h3 className="text-lg font-semibold text-zinc-950">Detected Technology Stack</h3>
          <p className="mt-1 text-sm text-zinc-500">Detected technologies are based on project files, dependencies, and configuration indicators.</p>
          <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-2">
            {analysis.technologies.length ? (
              analysis.technologies.map((technology) => <TechnologyBadge key={technology.id} technology={technology} />)
            ) : (
              <p className="text-sm text-zinc-500">No common technology indicators were detected.</p>
            )}
          </div>
        </div>

        <div className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-sentinel">
          <h3 className="text-lg font-semibold text-zinc-950">File Summary</h3>
          {analysis.file_summary ? (
            <dl className="mt-4 grid min-w-0 grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <dt className="text-zinc-500">Total files</dt>
                <dd className="mt-1 font-semibold text-zinc-950">{analysis.file_summary.total_files}</dd>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <dt className="text-zinc-500">Scanned</dt>
                <dd className="mt-1 font-semibold text-zinc-950">{analysis.file_summary.scanned_files}</dd>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <dt className="text-zinc-500">Skipped</dt>
                <dd className="mt-1 font-semibold text-zinc-950">{analysis.file_summary.skipped_files}</dd>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <dt className="text-zinc-500">Size</dt>
                <dd className="mt-1 font-semibold text-zinc-950">{formatBytes(analysis.file_summary.total_size_bytes)}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-4 text-sm text-zinc-500">No file summary is available.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, tone = "text-zinc-950" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p className={`mt-2 break-words text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function prioritySort(a: AnalysisDetail["findings"][number], b: AnalysisDetail["findings"][number]) {
  const priorityRank: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };
  const severityRank: Record<string, number> = { critical: 0, warning: 1, info: 2, passed: 3 };
  return (
    (priorityRank[a.priority ?? "P3"] ?? 3) - (priorityRank[b.priority ?? "P3"] ?? 3) ||
    (severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4)
  );
}

function riskTone(status: string) {
  if (status === "Excellent") return "text-emerald-700";
  if (status === "Strong") return "text-violet-700";
  if (status === "Needs work") return "text-amber-700";
  if (status === "Risky") return "text-orange-700";
  return "text-rose-700";
}
