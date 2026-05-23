import type { Severity } from "../types/api";

const classes: Record<Severity, string> = {
  critical: "border-rose-200 bg-rose-50 text-rose-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  info: "border-violet-200 bg-violet-50 text-violet-700",
  passed: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold uppercase tracking-wide ${classes[severity]}`}>
      {severity}
    </span>
  );
}
