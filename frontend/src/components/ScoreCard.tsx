import { scoreTone } from "../lib";
import type { ScoreExplanation } from "../types/api";

interface ScoreCardProps {
  label: string;
  score: number;
  explanation: ScoreExplanation;
}

export function ScoreCard({ label, score, explanation }: ScoreCardProps) {
  const status = explanation.status || statusForScore(score);
  const tone = statusTone(status);

  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-4 shadow-sentinel">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-600">{label}</p>
          <p className={`mt-2 text-3xl font-semibold ${scoreTone(score)}`}>{score}</p>
        </div>
        <span className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${tone.badge}`}>{status}</span>
      </div>
      <div className="mt-3 h-2 w-full rounded-full bg-zinc-100">
        <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
      <p className="mt-3 min-h-12 break-words text-xs leading-5 text-zinc-600">{explanation.explanation}</p>
      {(explanation.positives.length > 0 || explanation.deductions.length > 0) && (
        <div className="mt-3 min-w-0 space-y-2 border-t border-zinc-100 pt-3 text-xs">
          {explanation.positives.length > 0 && (
            <p className="break-words text-emerald-700">
              <span className="font-semibold">Positives:</span> {explanation.positives.slice(0, 2).join("; ")}
            </p>
          )}
          {explanation.deductions.length > 0 && (
            <p className="break-words text-rose-700">
              <span className="font-semibold">Deductions:</span> {explanation.deductions.slice(0, 2).join("; ")}
            </p>
          )}
        </div>
      )}
      <p className="mt-3 break-words border-t border-zinc-100 pt-3 text-xs leading-5 text-zinc-600">
        <span className="font-semibold text-zinc-900">Fix next:</span> {explanation.recommendation}
      </p>
    </section>
  );
}

function statusForScore(score: number): string {
  if (score >= 90) return "Excellent";
  if (score >= 75) return "Strong";
  if (score >= 60) return "Needs work";
  if (score >= 40) return "Risky";
  return "Critical";
}

function statusTone(status: string) {
  switch (status) {
    case "Excellent":
      return { badge: "border-emerald-200 bg-emerald-50 text-emerald-700", bar: "bg-emerald-500" };
    case "Strong":
      return { badge: "border-violet-200 bg-violet-50 text-violet-700", bar: "bg-violet-600" };
    case "Needs work":
      return { badge: "border-amber-200 bg-amber-50 text-amber-700", bar: "bg-amber-500" };
    case "Risky":
      return { badge: "border-orange-200 bg-orange-50 text-orange-700", bar: "bg-orange-500" };
    default:
      return { badge: "border-rose-200 bg-rose-50 text-rose-700", bar: "bg-rose-500" };
  }
}
