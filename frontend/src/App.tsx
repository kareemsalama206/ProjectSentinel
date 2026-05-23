import { Activity, History, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Dashboard } from "./pages/Dashboard";
import { FindingsPanel } from "./pages/FindingsPanel";
import { UploadPanel } from "./pages/UploadPanel";
import { API_BASE_URL, deleteAnalysis, fetchAnalyses, fetchAnalysis, resetAnalyses } from "./lib";
import type { AnalysisDetail, AnalysisSummary } from "./types/api";

function App() {
  const [recent, setRecent] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function loadRecent(): Promise<AnalysisSummary[]> {
    try {
      const analyses = await fetchAnalyses();
      setRecent(analyses);
      return analyses;
    } catch {
      setRecent([]);
      return [];
    }
  }

  async function loadAnalysis(id: number) {
    setIsLoading(true);
    setError(null);
    try {
      const detail = await fetchAnalysis(id);
      setSelected(detail);
      await loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load analysis.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteAnalysis(analysisId: number) {
    const confirmed = window.confirm("Delete this analysis? This removes the audit result from ProjectSentinel.");
    if (!confirmed) return;
    setError(null);
    try {
      await deleteAnalysis(analysisId);
      const analyses = await loadRecent();
      if (selected?.id === analysisId) {
        const next = analyses.find((analysis) => analysis.id !== analysisId);
        if (next) {
          await loadAnalysis(next.id);
        } else {
          setSelected(null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete analysis.");
    }
  }

  async function handleResetAll() {
    const confirmed = window.confirm("Reset all analyses? This removes all stored audit results.");
    if (!confirmed) return;
    setError(null);
    try {
      await resetAnalyses();
      setSelected(null);
      await loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset analyses.");
    }
  }

  useEffect(() => {
    loadRecent();
  }, []);

  return (
    <main className="min-h-screen min-w-0 overflow-x-hidden bg-canvas text-zinc-900">
      <div className="mx-auto flex min-w-0 w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
        <header className="flex min-w-0 flex-col gap-4 border-b border-zinc-200 pb-5 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-violet-200 bg-violet-100">
              <Activity className="h-5 w-5 text-violet-800" />
            </div>
            <div className="min-w-0">
              <p className="text-lg font-semibold text-zinc-950">ProjectSentinel</p>
              <p className="text-sm text-zinc-500">Universal software project audit and deployment readiness analyzer</p>
            </div>
          </div>
          <a className="text-sm font-medium text-violet-700 hover:text-violet-900" href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">
            API docs
          </a>
        </header>

        <UploadPanel
          onUploaded={(analysis) => {
            loadAnalysis(analysis.id);
          }}
        />

        {error && <div className="min-w-0 break-words rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
        {isLoading && <div className="min-w-0 rounded-lg border border-line bg-panel p-4 text-sm text-zinc-600">Loading analysis...</div>}

        <div className="grid min-w-0 gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-4 shadow-sentinel xl:sticky xl:top-6 xl:h-fit">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <History className="h-4 w-4 text-zinc-500" />
                <h2 className="font-semibold text-zinc-950">Recent Analyses</h2>
              </div>
              {recent.length > 0 && (
                <button className="inline-flex items-center gap-1.5 rounded-md border border-rose-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50" type="button" onClick={handleResetAll}>
                  <RotateCcw className="h-4 w-4" />
                  Reset all analyses
                </button>
              )}
            </div>
            <div className="mt-4 space-y-2">
              {recent.length ? (
                recent.map((analysis) => (
                  <div
                    key={analysis.id}
                    className={`min-w-0 overflow-hidden rounded-lg border ${
                      selected?.id === analysis.id
                        ? "border-violet-300 bg-violet-50"
                        : "border-zinc-200 bg-white hover:border-violet-200"
                    }`}
                  >
                    <button type="button" className="min-w-0 w-full p-3 text-left" onClick={() => loadAnalysis(analysis.id)}>
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-zinc-950">{analysis.project_name}</p>
                          <p className="mt-1 truncate text-xs text-zinc-500">{analysis.project_type}</p>
                        </div>
                        <span className="shrink-0 rounded-md bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">{analysis.overall_score}</span>
                      </div>
                      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-xs text-zinc-500">
                        <span>{new Date(analysis.created_at).toLocaleString()}</span>
                        <span className="text-rose-700">{analysis.severity_counts.critical ?? 0} critical</span>
                        <span className="text-amber-700">{analysis.severity_counts.warning ?? 0} warnings</span>
                      </div>
                    </button>
                    <div className="border-t border-zinc-100 px-3 py-2">
                      <button className="inline-flex items-center gap-1.5 text-xs font-medium text-rose-700 hover:text-rose-900" type="button" onClick={() => handleDeleteAnalysis(analysis.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm leading-6 text-zinc-500">No analyses yet. Upload a project ZIP to start.</p>
              )}
            </div>
          </aside>

          <section className="min-w-0 space-y-6">
            {selected ? (
              <>
                <Dashboard analysis={selected} onRefresh={() => loadAnalysis(selected.id)} />
                <FindingsPanel analysis={selected} />
              </>
            ) : (
              <div className="rounded-lg border border-line bg-panel p-8 text-center shadow-sentinel">
                <p className="text-lg font-medium text-zinc-950">No analysis selected</p>
                <p className="mt-2 text-sm text-zinc-500">Upload a project ZIP or choose a recent analysis to inspect the dashboard.</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default App;
