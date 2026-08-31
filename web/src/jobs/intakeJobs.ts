/**
 * Intake job model — shared by the provider and the tracker widget.
 *
 * The pipeline stage list is SERVER-authoritative (`app/services/intake/jobs.py`
 * STAGES). It is mirrored here only to turn a reported stage into "how far along
 * am I", and the mirror is deliberately narrow: if the server reports a stage we
 * do not know, progress stays indeterminate rather than guessing a percentage
 * (F01 AC-15 — a fabricated 40% is a fabricated number, Hard Rule 7).
 */

/** Ordered pipeline stages a customer's notice actually passes through. */
export const PIPELINE_STAGES = [
  "queued",
  "fetching",
  "extracting",
  "segmenting",
  "classifying",
  "profiling",
  "benchmarking",
  "scoring",
  "generating_findings",
] as const;

/** Stages the status endpoint may report that sit outside the progress bar. */
export const TERMINAL_STAGES = ["complete", "failed"] as const;

export const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  fetching: "Fetching the notice",
  extracting: "Extracting text",
  segmenting: "Decomposing into clauses",
  classifying: "Classifying clauses",
  profiling: "Profiling the organization",
  benchmarking: "Building the peer benchmark",
  scoring: "Scoring against peers",
  generating_findings: "Generating findings",
  awaiting_review: "Awaiting expert review",
  generating_report: "Generating the report",
  complete: "Complete",
  failed: "Could not be processed",
};

export type JobStatus = "queued" | "running" | "ready" | "failed";

export interface IntakeJob {
  jobId: string;
  /** What the user submitted — a URL, a filename, or "Pasted notice". */
  label: string;
  status: JobStatus;
  stage: string;
  /** The real notice id, present once persistence completes → links to the report. */
  assessmentId?: string;
  error?: string;
  submittedAt: number;
  /** Set when the user has acknowledged a finished job, so it stops being shown. */
  dismissed?: boolean;
}

/**
 * Fraction complete, or `null` when the server has not yet reported a stage we
 * can place. Null means "render an indeterminate bar" — never a guessed number.
 */
export function stageProgress(stage: string, status: JobStatus): number | null {
  if (status === "ready") return 1;
  if (status === "failed") return null;
  const i = (PIPELINE_STAGES as readonly string[]).indexOf(stage);
  if (i < 0) return null;
  // Completed stages out of total. The current stage is in flight, not done, so
  // the bar reports what has finished rather than flattering the progress.
  return i / PIPELINE_STAGES.length;
}

export function isTerminal(job: IntakeJob): boolean {
  return job.status === "ready" || job.status === "failed";
}
