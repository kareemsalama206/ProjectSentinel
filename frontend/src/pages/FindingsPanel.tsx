import { Filter } from "lucide-react";
import { useMemo, useState } from "react";
import { SeverityBadge } from "../components/SeverityBadge";
import type { AnalysisDetail, Finding, Severity } from "../types/api";

type FilterKey =
  | "all"
  | "critical"
  | "warning"
  | "passed"
  | "security"
  | "docker"
  | "testing"
  | "documentation"
  | "github"
  | "dependencies"
  | "structure";

const filters: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "critical", label: "Critical" },
  { key: "warning", label: "Warning" },
  { key: "passed", label: "Passed" },
  { key: "security", label: "Security" },
  { key: "docker", label: "Docker" },
  { key: "testing", label: "Testing" },
  { key: "documentation", label: "Documentation" },
  { key: "github", label: "GitHub" },
  { key: "dependencies", label: "Dependencies" },
  { key: "structure", label: "Structure" }
];

const severityOrder: Severity[] = ["critical", "warning", "info", "passed"];

export function FindingsPanel({ analysis }: { analysis: AnalysisDetail }) {
  const [active, setActive] = useState<FilterKey>("all");
  const filtered = useMemo(() => {
    if (active === "all") return analysis.findings;
    if (active === "critical" || active === "warning" || active === "passed") {
      return analysis.findings.filter((finding) => finding.severity === active);
    }
    return analysis.findings.filter((finding) => finding.category === active);
  }, [active, analysis.findings]);

  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-sentinel">
      <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-zinc-950">Findings Explorer</h3>
          <p className="mt-1 text-sm text-zinc-500">Grouped by severity with priority, impact, and deterministic recommendations.</p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-zinc-500" />
          {filters.map((filter) => (
            <button
              key={filter.key}
              className={active === filter.key ? "filter-chip-active" : "filter-chip"}
              onClick={() => setActive(filter.key)}
              type="button"
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 min-w-0 space-y-5">
        {severityOrder.map((severity) => {
          const group = filtered.filter((finding) => finding.severity === severity);
          if (!group.length) return null;
          return (
            <div key={severity}>
              <div className="mb-3 flex items-center gap-2">
                <SeverityBadge severity={severity} />
                <span className="text-sm text-zinc-500">{group.length} findings</span>
              </div>
              <div className="min-w-0 space-y-3">
                {group.map((finding) => (
                  <FindingCard key={finding.id} finding={finding} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  return (
    <article className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs font-semibold text-zinc-700">{finding.priority ?? "P3"}</span>
            <p className="min-w-0 break-words font-medium text-zinc-950">{finding.title}</p>
          </div>
          <p className="mt-1 text-sm capitalize text-zinc-500">{finding.category}</p>
        </div>
        {finding.file_path && (
          <p className="max-w-full shrink-0 break-all rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1 font-mono text-xs text-zinc-600 md:max-w-[45%]">
            {finding.file_path}
            {finding.line_number ? `:${finding.line_number}` : ""}
          </p>
        )}
      </div>
      <p className="mt-3 break-words text-sm leading-6 text-zinc-600">{finding.description}</p>
      {finding.why_it_matters && (
        <p className="mt-2 break-words text-sm leading-6 text-zinc-600">
          <span className="font-medium text-zinc-900">Why it matters:</span> {finding.why_it_matters}
        </p>
      )}
      <p className="mt-2 break-words text-sm leading-6 text-zinc-600">
        <span className="font-medium text-zinc-900">Recommendation:</span> {finding.recommendation}
      </p>
    </article>
  );
}
