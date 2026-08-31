/**
 * Background intake — progress must never be invented (F01 AC-15).
 *
 * The tracker's whole credibility rests on one rule: every advance comes from a
 * server-reported stage, and a stage we cannot place renders as an indeterminate
 * bar rather than a guessed percentage. A fabricated 40% is a fabricated number
 * (Hard Rule 7), and it is exactly the kind that looks harmless.
 */
import { describe, expect, it } from "vitest";
import { PIPELINE_STAGES, STAGE_LABELS, stageProgress, isTerminal } from "../jobs/intakeJobs";

describe("stageProgress — server-reported or nothing", () => {
  it("advances monotonically through the real pipeline stages", () => {
    const values = PIPELINE_STAGES.map(s => stageProgress(s, "running") as number);
    expect(values.every(v => typeof v === "number")).toBe(true);
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThan(values[i - 1]);
    }
  });

  it("never reports 100% while work is still running", () => {
    for (const s of PIPELINE_STAGES) {
      expect(stageProgress(s, "running")).toBeLessThan(1);
    }
  });

  it("returns null — indeterminate — for a stage it cannot place", () => {
    expect(stageProgress("some_future_server_stage", "running")).toBeNull();
    expect(stageProgress("", "running")).toBeNull();
    // A long-running job is NOT a failure and must not fake a percentage.
    expect(stageProgress("still_running", "running")).toBeNull();
  });

  it("reports complete only when the server said complete", () => {
    expect(stageProgress("complete", "ready")).toBe(1);
    expect(stageProgress("failed", "failed")).toBeNull();
  });

  it("every pipeline stage has customer-register wording", () => {
    for (const s of PIPELINE_STAGES) {
      expect(STAGE_LABELS[s], `missing label for ${s}`).toBeTruthy();
      // No house jargon or internal identifiers leak into the label (Rule 9).
      expect(STAGE_LABELS[s]).not.toMatch(/_|F-0\d\d|VCI|PGMS|SSRF/);
    }
  });

  it("terminal states are exactly ready and failed", () => {
    const base = { jobId: "j", label: "x", stage: "queued", submittedAt: 0 } as const;
    expect(isTerminal({ ...base, status: "ready" })).toBe(true);
    expect(isTerminal({ ...base, status: "failed" })).toBe(true);
    expect(isTerminal({ ...base, status: "running" })).toBe(false);
    expect(isTerminal({ ...base, status: "queued" })).toBe(false);
  });
});
