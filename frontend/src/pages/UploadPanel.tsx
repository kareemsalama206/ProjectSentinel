import { AlertTriangle, CheckCircle2, FileArchive, SearchCode, ShieldCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { formatBytes, uploadProjectZip } from "../lib";
import type { AnalysisSummary } from "../types/api";

interface UploadPanelProps {
  onUploaded: (analysis: AnalysisSummary) => void;
}

export function UploadPanel({ onUploaded }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function validateFile(nextFile: File | null) {
    setFile(nextFile);
    setError(null);
    if (!nextFile) {
      setValidation(null);
      return;
    }
    if (!nextFile.name.toLowerCase().endsWith(".zip")) {
      setValidation({ valid: false, message: "Invalid file type. Choose a .zip archive." });
      setError("Unsupported archive type. Upload a .zip file.");
      return;
    }
    if (nextFile.size === 0) {
      setValidation({ valid: false, message: "Invalid archive. The selected file is empty." });
      setError("The selected file is 0 bytes. Choose a non-empty ZIP archive.");
      return;
    }
    setValidation({ valid: true, message: "Ready for static analysis." });
  }

  async function submit() {
    if (!file || !validation?.valid) {
      setError("Choose a valid .zip project archive first.");
      return;
    }
    setIsUploading(true);
    setError(null);
    try {
      const analysis = await uploadProjectZip(file);
      onUploaded(analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-line bg-panel p-6 shadow-sentinel">
      <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-1.5 text-sm text-violet-800">
            <ShieldCheck className="h-4 w-4" />
            Safe static project analysis
          </div>
          <h1 className="text-3xl font-semibold text-zinc-950">ProjectSentinel</h1>
          <p className="mt-3 max-w-3xl break-words text-sm leading-6 text-zinc-600">
            Upload a software project ZIP to detect the stack, flag exposed secrets and risky configuration, evaluate README,
            testing, Docker, deployment, and GitHub readiness, then export a professional PDF report.
          </p>
        </div>
        <div className="grid min-w-0 shrink-0 grid-cols-2 gap-3 text-sm text-zinc-600 sm:min-w-64">
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
            <p className="text-zinc-500">Supported</p>
            <p className="mt-1 font-medium text-zinc-950">.zip only</p>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
            <p className="text-zinc-500">Execution</p>
            <p className="mt-1 font-medium text-zinc-950">Never runs code</p>
          </div>
        </div>
      </div>

      <div
        className="mt-6 min-w-0 overflow-hidden rounded-lg border border-dashed border-violet-300 bg-violet-50/60 p-5"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const dropped = event.dataTransfer.files[0];
          if (dropped) validateFile(dropped);
        }}
      >
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-violet-200 bg-violet-50">
                <FileArchive className="h-5 w-5 text-violet-700" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-zinc-950">Step 1: Choose ZIP File</p>
                <p className="mt-1 break-words text-xs text-zinc-500">Drag and drop or browse for a project archive.</p>
              </div>
            </div>
            <input
              ref={inputRef}
              className="hidden"
              type="file"
              accept=".zip,application/zip"
              onChange={(event) => validateFile(event.target.files?.[0] ?? null)}
            />
            <button className="btn-secondary mt-4 w-full sm:w-auto" onClick={() => inputRef.current?.click()} type="button">
              <Upload className="h-4 w-4" />
              Choose ZIP File
            </button>
            <p className="mt-3 break-words text-xs leading-5 text-zinc-500">Backend limits archive size and extracted file count. Binary files are skipped from deep scanning.</p>
          </div>

          <div className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50">
                <SearchCode className="h-5 w-5 text-emerald-700" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-zinc-950">Step 2: Analyze Project</p>
                <p className="mt-1 break-words text-xs text-zinc-500">Run deterministic checks after validation passes.</p>
              </div>
            </div>
            <div className="mt-4 min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm">
              {file ? (
                <dl className="grid min-w-0 gap-2 sm:grid-cols-2">
                  <div className="min-w-0">
                    <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">File name</dt>
                    <dd className="mt-1 break-all font-medium text-zinc-950">{file.name}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">File size</dt>
                    <dd className="mt-1 font-medium text-zinc-950">{formatBytes(file.size)}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">File type</dt>
                    <dd className="mt-1 break-words font-medium text-zinc-950">{file.type || "application/zip inferred from extension"}</dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Validation</dt>
                    <dd className={`mt-1 flex min-w-0 items-center gap-1.5 break-words font-medium ${validation?.valid ? "text-emerald-700" : "text-rose-700"}`}>
                      {validation?.valid && <CheckCircle2 className="h-4 w-4" />}
                      {validation?.message}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-zinc-500">No file selected yet.</p>
              )}
            </div>
            <button className="btn-primary mt-4 w-full sm:w-auto" onClick={submit} disabled={!validation?.valid || isUploading} type="button">
              <SearchCode className="h-4 w-4" />
              {isUploading ? "Analyzing project..." : "Analyze Project"}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          <p>{error}</p>
        </div>
      )}
    </section>
  );
}
