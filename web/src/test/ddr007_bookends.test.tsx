/**
 * DDR-007 (revised 2026-08-31) — the report is bookended, not littered.
 *
 * The per-surface "Intelligence, not legal advice" mark was replaced by a scope
 * statement at the front and one Disclosure at the end. The spec is explicit
 * that the mark may be removed ONLY in the change that ships both bookends: a
 * build with the mark gone and no Disclosure has quietly dropped a trust
 * mechanism rather than improved one. These tests are that gate.
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Disclosure } from "../report/sections/Disclosure";

afterEach(cleanup);

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const sectionsDir = resolve(here, "../report/sections");

const BANNED_TERMS = readFileSync(resolve(repoRoot, "scripts/data/banned_terms.txt"), "utf-8")
  .split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("DDR-007 revised — scope up front, one disclosure at the end", () => {
  it("no report section carries the retired per-surface mark", () => {
    const offenders = readdirSync(sectionsDir)
      .filter(f => f.endsWith(".tsx"))
      .filter(f => readFileSync(resolve(sectionsDir, f), "utf-8").includes("IntelligenceMark"));
    expect(offenders).toEqual([]);
  });

  it("the closing Disclosure exists and states both what the report is and is not", () => {
    render(<Disclosure cohortSize={42} cohortDate="2026-08-31" />);
    expect(screen.getByTestId("report-disclosure")).toBeInTheDocument();
    expect(screen.getByText(/What this report is\./)).toBeInTheDocument();
    expect(screen.getByText(/What it is not\./)).toBeInTheDocument();
    // The substance the retired mark used to carry must survive the move.
    expect(screen.getByTestId("report-disclosure").textContent)
      .toMatch(/not legal advice/i);
  });

  it("the Disclosure is rendered by ReportView — the mark is never dropped alone", () => {
    const view = readFileSync(resolve(here, "../report/ReportView.tsx"), "utf-8");
    expect(view).toMatch(/<Disclosure\b/);
  });

  it("the Disclosure copy passes the banned-term filter (Hard Rule 1)", () => {
    render(<Disclosure cohortSize={42} cohortDate="2026-08-31" />);
    const text = screen.getByTestId("report-disclosure").textContent ?? "";
    const hits = BANNED_TERMS.filter(t => new RegExp(`\\b${escapeRe(t)}\\b`, "i").test(text));
    expect(hits).toEqual([]);
  });
});
