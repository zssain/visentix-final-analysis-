/**
 * Background-task model — shared by the provider and the tracker widget.
 *
 * ONE task system, not one per feature. Intake was asynchronous first and is the
 * pattern generalized here; re-assessment, quarterly build and report export
 * join it rather than each growing their own progress affordance. A reader who
 * has to look in three places to find out what is running has lost track of it.
 *
 * Stage lists are SERVER-authoritative. They are mirrored here only to turn a
 * reported stage into "how far along am I", and the mirror is deliberately
 * narrow: an unrecognised stage leaves progress INDETERMINATE rather than
 * guessing a percentage — a fabricated 40% is a fabricated number (Hard Rule 7,
 * F01 AC-15).
 */

export type TaskKind =
  | "intake"
  | "reassessment"
  | "quarterly_build"
  | "report_pdf";

export type TaskStatus = "queued" | "running" | "ready" | "failed";

export interface Task {
  taskId: string;
  kind: TaskKind;
  /** What the reader asked for, in their words. Shown in the tracker. */
  label: string;
  status: TaskStatus;
  stage: string;
  submittedAt: number;
  /** Set when the task produces something openable. */
  resultId?: string;
  /** Where "open" goes when it finishes. Absent = nothing to open. */
  resultHref?: string;
  error?: string;
  dismissed?: boolean;
}

/** Status endpoint per kind. Kept beside the kinds so adding one is one edit. */
export const TASK_STATUS_URL: Record<TaskKind, (id: string) => string> = {
  intake:          id => `/assessments/${id}/status`,
  reassessment:    id => `/tasks/${id}`,
  quarterly_build: id => `/tasks/${id}`,
  report_pdf:      id => `/tasks/${id}`,
};

/** Ordered stages per kind, for the progress bar. */
export const TASK_STAGES: Record<TaskKind, readonly string[]> = {
  intake: [
    "queued", "fetching", "extracting", "segmenting", "classifying",
    "profiling", "benchmarking", "scoring", "generating_findings",
  ],
  reassessment:    ["queued", "loading_notices", "scoring", "writing_snapshots"],
  quarterly_build: ["queued", "aggregating", "suppressing", "rendering"],
  report_pdf:      ["queued", "rendering"],
};

export const TERMINAL_STAGES = ["complete", "failed"] as const;

export const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  // intake
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
  // reassessment
  loading_notices: "Loading stored notices",
  writing_snapshots: "Writing new snapshots",
  // quarterly
  aggregating: "Aggregating the corpus",
  suppressing: "Applying suppression rules",
  rendering: "Rendering",
  // terminal
  complete: "Complete",
  failed: "Could not be completed",
  still_running: "Still processing",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage.replace(/_/g, " ");
}

/**
 * Fraction complete, or `null` when the stage is not on the known list.
 * Null renders an indeterminate bar — never an invented percentage.
 */
export function stageProgress(kind: TaskKind, stage: string): number | null {
  // Complete is the only 1.0. Everything mid-pipeline stays below it, so a bar
  // can never read "done" while work is still running.
  if (stage === "complete") return 1;
  const stages = TASK_STAGES[kind];
  if (!stages) return null;
  const i = stages.indexOf(stage);
  if (i < 0) return null;
  return (i + 1) / (stages.length + 1);
}

export function isTerminal(task: Pick<Task, "status" | "stage">): boolean {
  return task.status === "ready" || task.status === "failed" ||
         (TERMINAL_STAGES as readonly string[]).includes(task.stage);
}
