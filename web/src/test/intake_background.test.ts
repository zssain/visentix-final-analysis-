/**
 * Background intake — progress must never be invented (F01 AC-15).
 *
 * The tracker's whole credibility rests on one rule: every advance comes from a
 * server-reported stage, and a stage we cannot place renders as an indeterminate
 * bar rather than a guessed percentage. A fabricated 40% is a fabricated number
 * (Hard Rule 7), and it is exactly the kind that looks harmless.
 */
import { describe, expect, it } from "vitest";
import { TASK_STAGES, STAGE_LABELS, stageProgress, isTerminal } from "../jobs/tasks";

/** The intake pipeline, now one kind among several in the shared task model. */
const PIPELINE_STAGES = TASK_STAGES.intake;

describe("stageProgress — server-reported or nothing", () => {
  it("advances monotonically through the real pipeline stages", () => {
    const values = PIPELINE_STAGES.map((s: string) => stageProgress("intake", s) as number);
    expect(values.every(v => typeof v === "number")).toBe(true);
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThan(values[i - 1]);
    }
  });

  it("never reports 100% while work is still running", () => {
    for (const s of PIPELINE_STAGES) {
      expect(stageProgress("intake", s)).toBeLessThan(1);
    }
  });

  it("returns null — indeterminate — for a stage it cannot place", () => {
    expect(stageProgress("intake", "some_future_server_stage")).toBeNull();
    expect(stageProgress("intake", "")).toBeNull();
    // A long-running job is NOT a failure and must not fake a percentage.
    expect(stageProgress("intake", "still_running")).toBeNull();
  });

  it("reports complete only when the server said complete", () => {
    expect(stageProgress("intake", "complete")).toBe(1);
    expect(stageProgress("intake", "failed")).toBeNull();
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

describe("task model — one system, several kinds", () => {
  it("every kind has ordered stages and never reports 100% mid-pipeline", () => {
    for (const kind of Object.keys(TASK_STAGES) as (keyof typeof TASK_STAGES)[]) {
      const stages = TASK_STAGES[kind];
      expect(stages.length).toBeGreaterThan(0);
      const values = stages.map(s => stageProgress(kind, s) as number);
      for (const v of values) expect(v).toBeLessThan(1);
      for (let i = 1; i < values.length; i++) expect(values[i]).toBeGreaterThan(values[i - 1]);
    }
  });

  it("every stage across every kind has customer-register wording", () => {
    for (const kind of Object.keys(TASK_STAGES) as (keyof typeof TASK_STAGES)[]) {
      for (const s of TASK_STAGES[kind]) {
        expect(STAGE_LABELS[s], `stage "${s}" (${kind}) has no label`).toBeTruthy();
        expect(STAGE_LABELS[s]).not.toMatch(/_/);
      }
    }
  });

  it("an unknown kind is indeterminate, never a guessed percentage", () => {
    // @ts-expect-error — deliberately probing an unregistered kind
    expect(stageProgress("not_a_kind", "queued")).toBeNull();
  });

  it("terminal detection does not depend on the kind", () => {
    expect(isTerminal({ status: "ready", stage: "complete" })).toBe(true);
    expect(isTerminal({ status: "failed", stage: "failed" })).toBe(true);
    expect(isTerminal({ status: "running", stage: "scoring" })).toBe(false);
    // "still_running" is a long job, NOT a finished one — it must keep polling.
    expect(isTerminal({ status: "running", stage: "still_running" })).toBe(false);
  });
});
