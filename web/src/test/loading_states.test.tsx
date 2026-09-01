/**
 * Loading states.
 *
 * The bug this guards is not "the spinner is ugly". While the two dashboard
 * requests were in flight the page rendered three STATEMENTS OF FACT —
 * "No report yet", "No scores computed yet", "Active Assessments (0)" — about
 * data that had not arrived, two of which were wrong within the second. It is
 * the same failure as every other one this session: absence asserted before
 * absence is known.
 *
 * A loading state must say "not yet known". An empty state says "there is
 * none". They are different claims and must never share a silhouette.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton, SkeletonGroup } from "@/components/ui/skeleton";

describe("Skeleton", () => {
  it("is hidden from assistive tech — a grey box has nothing to read out", () => {
    const { container } = render(<Skeleton className="h-4 w-20" />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("holds still under reduced motion, and stays visible while it does", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild!;
    // An indefinite pulse is exactly what prefers-reduced-motion exists for.
    expect(el).toHaveClass("motion-reduce:animate-none");
    // ...but it must still read as a placeholder, so it does not fade away.
    expect(el).toHaveClass("motion-reduce:opacity-80");
  });
});

describe("SkeletonGroup", () => {
  it("announces the wait once, and says WHAT is loading", () => {
    render(
      <SkeletonGroup label="Loading assessments">
        <Skeleton /><Skeleton /><Skeleton />
      </SkeletonGroup>
    );
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    // "Loading", unqualified, tells a screen-reader user nothing about which of
    // the four panels on this page is still working.
    expect(status).toHaveAccessibleName("Loading assessments");
  });

  it("the boxes inside it are not each announced", () => {
    render(
      <SkeletonGroup label="Loading assessments">
        <Skeleton /><Skeleton />
      </SkeletonGroup>
    );
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});

// ── The dashboard's own copy ─────────────────────────────────

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const SOURCE = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../pages/customer/Dashboard.tsx"),
  "utf-8",
).replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

describe("the dashboard never asserts absence before the data lands", () => {
  it("gates the report card on `loading` before it can say 'No report yet'", () => {
    // The empty state must sit AFTER the loading branch, not instead of it.
    const loadingBranch = SOURCE.indexOf("{loading ? (");
    const emptyState = SOURCE.indexOf("No report yet");
    expect(loadingBranch).toBeGreaterThan(-1);
    expect(emptyState).toBeGreaterThan(loadingBranch);
  });

  it("gates the score panel on `loading` before 'No scores computed yet'", () => {
    expect(SOURCE).toMatch(/\{loading \? \([\s\S]*?\) : overallScore != null \? \(/);
  });

  it("does not print a count of 0 while the list is still loading", () => {
    // "Active Assessments (0)" beside a spinner is a contradiction the reader
    // has to resolve.
    expect(SOURCE).toMatch(/Active Assessments\{loading \? "" :/);
  });
});
