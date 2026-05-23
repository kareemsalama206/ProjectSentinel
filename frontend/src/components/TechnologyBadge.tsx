import type { Technology } from "../types/api";

export function TechnologyBadge({ technology }: { technology: Technology }) {
  return (
    <article className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words font-semibold text-zinc-950">{technology.name}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-violet-700">{technology.category}</p>
        </div>
        <span className="shrink-0 rounded-md border border-violet-200 bg-violet-50 px-2 py-1 text-xs font-semibold capitalize text-violet-700">
          {technology.confidence ?? "not checked"}
        </span>
      </div>
      <dl className="mt-3 min-w-0 space-y-2 text-xs leading-5 text-zinc-600">
        <div className="min-w-0">
          <dt className="font-semibold text-zinc-800">Evidence</dt>
          <dd className="break-all font-mono text-zinc-700">{technology.evidence_file ?? "Not available"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold text-zinc-800">Reason</dt>
          <dd className="break-words">{technology.reason ?? "Possible technology detected from project indicators."}</dd>
        </div>
      </dl>
    </article>
  );
}
