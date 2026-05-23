import type { AnalysisDetail, AnalysisSummary } from "./types/api";

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8003";

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail || "Request failed.";
  } catch {
    return "Request failed.";
  }
}

export async function uploadProjectZip(file: File): Promise<AnalysisSummary> {
  const data = new FormData();
  data.append("file", file);
  const response = await fetch(`${API_BASE_URL}/analyses/upload`, {
    method: "POST",
    body: data
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function fetchAnalyses(): Promise<AnalysisSummary[]> {
  const response = await fetch(`${API_BASE_URL}/analyses`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function fetchAnalysis(id: number): Promise<AnalysisDetail> {
  const response = await fetch(`${API_BASE_URL}/analyses/${id}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function deleteAnalysis(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/analyses/${id}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export async function resetAnalyses(): Promise<number> {
  const response = await fetch(`${API_BASE_URL}/analyses/reset`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const payload = (await response.json()) as { deleted_count: number };
  return payload.deleted_count;
}

export function reportUrl(id: number): string {
  return `${API_BASE_URL}/analyses/${id}/report`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function scoreTone(score: number): string {
  if (score >= 85) return "text-emerald-700";
  if (score >= 65) return "text-amber-700";
  return "text-rose-700";
}
