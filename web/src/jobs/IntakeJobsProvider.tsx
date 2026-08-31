/**
 * IntakeJobsProvider — assessment jobs keep running when you leave the page.
 *
 * Intake is asynchronous on the server (AGENTS.md §3a / QA-011: `POST
 * /assessments/async` returns 202 + a job handle, progress lives in server state
 * and is polled). The UI did not honour that: polling lived inside the Intake
 * page, so navigating away lost the only view of a job that was still running.
 *
 * This lifts tracking to the app shell. Jobs survive navigation and a full page
 * refresh (the handles are persisted), and every progress reading comes from
 * `GET /assessments/{jobId}/status` — never a client-side timer, never an
 * animation that advances while the server is silent (F01 AC-15).
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import { api } from "../lib/api";
import { isTerminal, type IntakeJob, type JobStatus } from "./intakeJobs";

const STORAGE_KEY = "visentix.intakeJobs.v1";
const POLL_MIN_MS = 1200;
const POLL_MAX_MS = 5000;
/** Stop polling a job that has not moved for this long; it is not lost, and the
 *  server keeps working — we simply stop asking and say so. */
const POLL_MAX_WALL_MS = 10 * 60 * 1000;

interface IntakeJobsValue {
  jobs: IntakeJob[];
  /** Jobs worth showing in the tracker: everything not dismissed. */
  visibleJobs: IntakeJob[];
  track: (job: Pick<IntakeJob, "jobId" | "label" | "stage" | "status">) => void;
  dismiss: (jobId: string) => void;
  dismissAllFinished: () => void;
}

const IntakeJobsContext = createContext<IntakeJobsValue | null>(null);

function load(): IntakeJob[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as IntakeJob[]) : [];
  } catch {
    // Private window, cleared storage, or a browser blocking site data — start
    // empty rather than breaking the shell.
    return [];
  }
}

function save(jobs: IntakeJob[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
  } catch { /* storage unavailable — tracking still works for this session */ }
}

export function IntakeJobsProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<IntakeJob[]>(load);
  // Jobs currently being polled, so a re-render never starts a second loop.
  const polling = useRef<Set<string>>(new Set());

  useEffect(() => { save(jobs); }, [jobs]);

  const patch = useCallback((jobId: string, next: Partial<IntakeJob>) => {
    setJobs(items => items.map(j => (j.jobId === jobId ? { ...j, ...next } : j)));
  }, []);

  const poll = useCallback(async function pollLoop(jobId: string, intervalMs: number, startedAt: number) {
    if (Date.now() - startedAt > POLL_MAX_WALL_MS) {
      // Honest stop: the job may well still be running server-side, so this is
      // not reported as a failure.
      patch(jobId, {
        stage: "still_running",
        error: "Still processing — this is taking longer than usual. It keeps running; reopen the report later.",
      });
      polling.current.delete(jobId);
      return;
    }
    try {
      const s = await api.get(`/assessments/${jobId}/status`) as {
        status: string; stage: string; assessment_id?: string; error?: string;
      };
      if (s.status === "complete") {
        patch(jobId, { status: "ready", stage: "complete", assessmentId: s.assessment_id });
        polling.current.delete(jobId);
        return;
      }
      if (s.status === "failed") {
        patch(jobId, { status: "failed", stage: "failed", error: s.error });
        polling.current.delete(jobId);
        return;
      }
      patch(jobId, { status: "running", stage: s.stage || "queued" });
      const next = Math.min(intervalMs + 400, POLL_MAX_MS);
      setTimeout(() => pollLoop(jobId, next, startedAt), next);
    } catch {
      // A transient network/auth blip must not kill tracking — back off further
      // and try again inside the wall-clock budget.
      const next = Math.min(intervalMs + 900, POLL_MAX_MS);
      setTimeout(() => pollLoop(jobId, next, startedAt), next);
    }
  }, [patch]);

  // Resume polling for anything unfinished — on mount (i.e. after a refresh or a
  // fresh navigation into the app) and whenever a new job is tracked.
  useEffect(() => {
    for (const job of jobs) {
      if (isTerminal(job) || polling.current.has(job.jobId)) continue;
      polling.current.add(job.jobId);
      poll(job.jobId, POLL_MIN_MS, job.submittedAt || Date.now());
    }
  }, [jobs, poll]);

  const track = useCallback<IntakeJobsValue["track"]>((job) => {
    setJobs(items => [
      ...items.filter(j => j.jobId !== job.jobId),
      { ...job, status: job.status as JobStatus, submittedAt: Date.now() },
    ]);
  }, []);

  const dismiss = useCallback((jobId: string) => {
    setJobs(items => items.map(j => (j.jobId === jobId ? { ...j, dismissed: true } : j)));
  }, []);

  const dismissAllFinished = useCallback(() => {
    setJobs(items => items.map(j => (isTerminal(j) ? { ...j, dismissed: true } : j)));
  }, []);

  const value = useMemo<IntakeJobsValue>(() => ({
    jobs,
    visibleJobs: jobs.filter(j => !j.dismissed),
    track, dismiss, dismissAllFinished,
  }), [jobs, track, dismiss, dismissAllFinished]);

  return <IntakeJobsContext.Provider value={value}>{children}</IntakeJobsContext.Provider>;
}

export function useIntakeJobs(): IntakeJobsValue {
  const ctx = useContext(IntakeJobsContext);
  if (!ctx) throw new Error("useIntakeJobs must be used inside IntakeJobsProvider");
  return ctx;
}
