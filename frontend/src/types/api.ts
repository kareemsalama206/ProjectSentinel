export type Severity = "critical" | "warning" | "info" | "passed";

export interface Technology {
  id: number;
  name: string;
  category: string;
  evidence_file?: string | null;
  reason?: string | null;
  confidence?: "high" | "medium" | "low" | string | null;
}

export interface Finding {
  id: number;
  category: string;
  severity: Severity;
  priority?: string | null;
  title: string;
  description: string;
  why_it_matters?: string | null;
  recommendation: string;
  file_path?: string | null;
  line_number?: number | null;
  created_at: string;
}

export interface FileSummary {
  total_files: number;
  scanned_files: number;
  skipped_files: number;
  total_size_bytes: number;
}

export interface ScoreExplanation {
  status: string;
  explanation: string;
  positives: string[];
  deductions: string[];
  recommendation: string;
}

export interface ScoreExplanations {
  overall: ScoreExplanation;
  security: ScoreExplanation;
  documentation: ScoreExplanation;
  testing: ScoreExplanation;
  docker: ScoreExplanation;
  github: ScoreExplanation;
  deployment: ScoreExplanation;
  maintainability: ScoreExplanation;
}

export interface AnalysisSummary {
  id: number;
  project_name: string;
  file_name: string;
  project_type: string;
  overall_score: number;
  security_score: number;
  documentation_score: number;
  testing_score: number;
  docker_score: number;
  github_score: number;
  deployment_score: number;
  maintainability_score: number;
  created_at: string;
  technologies: Technology[];
  severity_counts: Record<Severity, number>;
  score_explanations: ScoreExplanations;
  file_summary?: FileSummary | null;
}

export interface AnalysisDetail extends AnalysisSummary {
  findings: Finding[];
}
