/**
 * TasksProvider — background work keeps running when you leave the page.
 *
 * Generalized from IntakeJobsProvider. Intake was asynchronous on the server
 * while the UI polled from inside the Intake page, so navigating away lost the
 * only view of a job still running. That fix now applies to every long
 * operation, not just intake: re-assessment, quarterly build and report export
 * hand off the same way and appear in the same tracker.
 *
 * Every progress reading comes from the server. Never a client-side timer,
 * never an animation that advances while the server is silent (F01 AC-15).
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import { api } from "../lib/api";
import { TASK_STATUS_URL, isTerminal, type Task, type TaskKind, type TaskStatus } from "./tasks";

const STORAGE_KEY = "visentix.tasks.v1";
/** Read once at load so a v1-intake user's in-flight jobs are not orphaned. */
const LEGACY_KEY = "visentix.intakeJobs.v1";
const POLL_MIN_MS = 1200;
const POLL_MAX_MS = 5000;
/** Stop polling a task that has not finished inside this budget. It is not lost
 *  and the server keeps working — we simply stop asking, and say so. */
const POLL_MAX_WALL_MS = 10 * 60 * 1000;

export interface TasksValue {
  tasks: Task[];
  /** Tasks worth showing in the tracker: everything not dismissed. */
  visibleTasks: Task[];
  track: (task: Omit<Task, "submittedAt" | "dismissed">) => void;
  dismiss: (taskId: string) => void;
  dismissAllFinished: () => void;
}

const TasksContext = createContext<TasksValue | null>(null);

function load(): Task[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as Task[];
    }
    // Migrate any intake jobs still in flight from the pre-generalization key.
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy) {
      const parsed = JSON.parse(legacy);
      if (Array.isArray(parsed)) {
        return parsed.map((j: Record<string, unknown>) => ({
          taskId: String(j.jobId ?? ""),
          kind: "intake" as TaskKind,
          label: String(j.label ?? "Assessment"),
          status: (j.status as TaskStatus) ?? "running",
          stage: String(j.stage ?? "queued"),
          submittedAt: Number(j.submittedAt) || Date.now(),
          resultId: j.assessmentId as string | undefined,
          resultHref: j.assessmentId ? `/reports/${j.assessmentId}` : undefined,
          error: j.error as string | undefined,
          dismissed: Boolean(j.dismissed),
        })).filter(t => t.taskId);
      }
    }
    return [];
  } catch {
    // Private window, cleared storage, or a browser blocking site data — start
    // empty rather than breaking the shell.
    return [];
  }
}

function save(tasks: Task[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks)); }
  catch { /* storage unavailable — tracking still works for this session */ }
}

export function TasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>(load);
  // Tasks currently being polled, so a re-render never starts a second loop.
  const polling = useRef<Set<string>>(new Set());

  useEffect(() => { save(tasks); }, [tasks]);

  const patch = useCallback((taskId: string, next: Partial<Task>) => {
    setTasks(items => items.map(t => (t.taskId === taskId ? { ...t, ...next } : t)));
  }, []);

  const poll = useCallback(async function pollLoop(
    taskId: string, kind: TaskKind, intervalMs: number, startedAt: number,
  ) {
    if (Date.now() - startedAt > POLL_MAX_WALL_MS) {
      // Honest stop: the task may well still be running server-side, so this is
      // reported as "still processing", never as a failure.
      patch(taskId, {
        stage: "still_running",
        error: "Still processing — this is taking longer than usual. It keeps running; check back later.",
      });
      polling.current.delete(taskId);
      return;
    }
    try {
      const url = TASK_STATUS_URL[kind]?.(taskId);
      if (!url) { polling.current.delete(taskId); return; }
      const s = await api.get(url) as {
        status: string; stage: string; assessment_id?: string; result_id?: string; error?: string;
      };
      const resultId = s.result_id ?? s.assessment_id;
      if (s.status === "complete") {
        patch(taskId, {
          status: "ready", stage: "complete", resultId,
          resultHref: kind === "intake" && resultId ? `/reports/${resultId}` : undefined,
        });
        polling.current.delete(taskId);
        return;
      }
      if (s.status === "failed") {
        patch(taskId, { status: "failed", stage: "failed", error: s.error });
        polling.current.delete(taskId);
        return;
      }
      patch(taskId, { status: "running", stage: s.stage || "queued" });
      const next = Math.min(intervalMs + 400, POLL_MAX_MS);
      setTimeout(() => pollLoop(taskId, kind, next, startedAt), next);
    } catch {
      // A transient network/auth blip must not kill tracking — back off further
      // and retry inside the wall-clock budget.
      const next = Math.min(intervalMs + 900, POLL_MAX_MS);
      setTimeout(() => pollLoop(taskId, kind, next, startedAt), next);
    }
  }, [patch]);

  // Resume polling anything unfinished — on mount (after a refresh or a fresh
  // navigation into the app) and whenever a new task is tracked.
  useEffect(() => {
    for (const t of tasks) {
      if (isTerminal(t) || polling.current.has(t.taskId)) continue;
      polling.current.add(t.taskId);
      poll(t.taskId, t.kind, POLL_MIN_MS, t.submittedAt || Date.now());
    }
  }, [tasks, poll]);

  const track = useCallback<TasksValue["track"]>((task) => {
    setTasks(items => [
      ...items.filter(t => t.taskId !== task.taskId),
      { ...task, submittedAt: Date.now() },
    ]);
  }, []);

  const dismiss = useCallback((taskId: string) => {
    setTasks(items => items.map(t => (t.taskId === taskId ? { ...t, dismissed: true } : t)));
  }, []);

  const dismissAllFinished = useCallback(() => {
    setTasks(items => items.map(t => (isTerminal(t) ? { ...t, dismissed: true } : t)));
  }, []);

  const value = useMemo<TasksValue>(() => ({
    tasks,
    visibleTasks: tasks.filter(t => !t.dismissed),
    track, dismiss, dismissAllFinished,
  }), [tasks, track, dismiss, dismissAllFinished]);

  return <TasksContext.Provider value={value}>{children}</TasksContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTasks(): TasksValue {
  const ctx = useContext(TasksContext);
  if (!ctx) throw new Error("useTasks must be used inside TasksProvider");
  return ctx;
}
