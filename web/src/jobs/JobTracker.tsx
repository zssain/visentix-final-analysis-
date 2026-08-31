/**
 * JobTracker — the floating "still working" panel, bottom-right.
 *
 * Submitting a notice should not pin you to the intake page. This is the surface
 * that makes leaving safe: it follows you across routes, survives a refresh, and
 * is the one place a running assessment reports itself.
 *
 * Honesty rules it inherits (F01 AC-15/16):
 *  - every advance comes from a server status response; nothing animates on a timer;
 *  - a stage the client cannot place renders as an indeterminate bar, never a
 *    guessed percentage;
 *  - a long-running job says so plainly and is never reported as failed.
 *
 * It renders nothing at all when there is nothing to report (DDR-011).
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useIntakeJobs } from "./IntakeJobsProvider";
import { STAGE_LABELS, isTerminal, stageProgress } from "./intakeJobs";
import "./job-tracker.css";

export function JobTracker() {
  const { visibleJobs, dismiss, dismissAllFinished } = useIntakeJobs();
  const [open, setOpen] = useState(true);

  if (visibleJobs.length === 0) return null;

  const running = visibleJobs.filter(j => !isTerminal(j)).length;
  const finished = visibleJobs.length - running;
  const heading = running > 0
    ? `${running} assessment${running > 1 ? "s" : ""} in progress`
    : `${finished} assessment${finished > 1 ? "s" : ""} ready`;

  return (
    <aside className="job-tracker" aria-label="Assessment progress">
      <div className="jt-head">
        <button
          type="button"
          className="jt-toggle"
          aria-expanded={open}
          onClick={() => setOpen(o => !o)}
        >
          {running > 0 && <span className="jt-spinner" aria-hidden="true" />}
          <span className="jt-heading">{heading}</span>
          <span className="jt-chevron" aria-hidden="true">{open ? "▾" : "▴"}</span>
        </button>
        {finished > 0 && (
          <button type="button" className="jt-clear" onClick={dismissAllFinished}>
            Clear finished
          </button>
        )}
      </div>

      {open && (
        <ul className="jt-list">
          {visibleJobs.map(job => {
            const pct = stageProgress(job.stage, job.status);
            const stalled = job.stage === "still_running";
            return (
              <li key={job.jobId} className={`jt-item jt-${job.status}`}>
                <div className="jt-row">
                  <span className="jt-label" title={job.label}>{job.label}</span>
                  <button
                    type="button"
                    className="jt-dismiss"
                    aria-label={`Stop showing ${job.label}`}
                    onClick={() => dismiss(job.jobId)}
                  >×</button>
                </div>

                {!isTerminal(job) && (
                  <>
                    <div
                      className={`jt-bar ${pct === null ? "indeterminate" : ""}`}
                      role="progressbar"
                      aria-label={`${job.label} progress`}
                      {...(pct !== null
                        ? { "aria-valuenow": Math.round(pct * 100), "aria-valuemin": 0, "aria-valuemax": 100 }
                        : {})}
                    >
                      <div
                        className="jt-bar-fill"
                        style={pct !== null ? { width: `${Math.round(pct * 100)}%` } : undefined}
                      />
                    </div>
                    <span className="jt-stage">
                      {stalled
                        ? "Still processing — it keeps running, you can close this"
                        : STAGE_LABELS[job.stage] ?? "Working"}
                      {pct !== null && !stalled && <> · {Math.round(pct * 100)}%</>}
                    </span>
                  </>
                )}

                {job.status === "ready" && job.assessmentId && (
                  <Link className="jt-open" to={`/reports/${job.assessmentId}`} onClick={() => dismiss(job.jobId)}>
                    Open report →
                  </Link>
                )}
                {job.status === "failed" && (
                  <span className="jt-error">{job.error || "Could not be processed."}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
