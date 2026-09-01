/**
 * TaskTracker — the floating "still working" panel, bottom-right.
 *
 * THE one place background work reports itself, whatever started it. A second
 * progress affordance elsewhere is how a reader loses track of what is running,
 * so every long operation lands here: intake, re-assessment, quarterly build,
 * report export.
 *
 * Honesty rules (F01 AC-15/16):
 *  - every advance comes from a server status response; nothing animates on a timer;
 *  - a stage the client cannot place renders indeterminate, never a guessed percentage;
 *  - a long-running task says so plainly and is never reported as failed.
 *
 * It renders nothing at all when there is nothing to report (DDR-011).
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, X } from "lucide-react";
import { useTasks } from "./TasksProvider";
import { isTerminal, stageLabel, stageProgress } from "./tasks";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function TaskTracker() {
  const { visibleTasks, dismiss, dismissAllFinished } = useTasks();
  const [open, setOpen] = useState(true);

  if (visibleTasks.length === 0) return null;

  const running = visibleTasks.filter(t => !isTerminal(t)).length;
  const finished = visibleTasks.length - running;
  // Kind-neutral wording: this panel now carries more than assessments.
  const heading = running > 0
    ? `${running} task${running > 1 ? "s" : ""} in progress`
    : `${finished} task${finished > 1 ? "s" : ""} finished`;

  return (
    <aside
      className="fixed bottom-4 right-4 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-lg border bg-card shadow-lg"
      aria-label="Background task progress"
    >
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <button
          type="button"
          className="flex flex-1 items-center gap-1.5 text-left text-sm font-semibold"
          aria-expanded={open}
          onClick={() => setOpen(o => !o)}
        >
          <ChevronDown className={cn("size-4 transition-transform motion-reduce:transition-none", !open && "-rotate-90")} />
          {heading}
        </button>
        {finished > 0 && (
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={dismissAllFinished}>
            Clear finished
          </Button>
        )}
      </div>

      {open && (
        <ul className="max-h-80 overflow-y-auto">
          {visibleTasks.map(t => {
            const pct = stageProgress(t.kind, t.stage);
            const done = isTerminal(t);
            return (
              <li key={t.taskId} className="border-b px-3 py-2.5 last:border-0">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{t.label}</div>
                    <div className={cn(
                      "text-xs",
                      t.status === "failed" ? "text-[var(--standing-bad)]" : "text-muted-foreground"
                    )}>
                      {t.error ?? stageLabel(t.stage)}
                    </div>
                  </div>
                  <Button
                    variant="ghost" size="icon" className="size-6 shrink-0"
                    onClick={() => dismiss(t.taskId)}
                    aria-label={`Dismiss ${t.label}`}
                  >
                    <X />
                  </Button>
                </div>

                {!done && (
                  /* An unplaceable stage gives an indeterminate bar rather than
                     a guessed percentage (Hard Rule 7). */
                  <Progress
                    value={pct === null ? undefined : Math.round(pct * 100)}
                    className={cn("mt-2 h-1", pct === null && "animate-pulse motion-reduce:animate-none")}
                    aria-label={pct === null ? "Progress unknown" : `${Math.round(pct * 100)}% complete`}
                  />
                )}

                {/* Exactly one next action when it finishes (D2 rule 4). */}
                {t.status === "ready" && t.resultHref && (
                  <Button asChild size="sm" className="mt-2 h-7">
                    <Link to={t.resultHref} onClick={() => dismiss(t.taskId)}>Open</Link>
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
