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
    // Anchored on the SUBSTANCE, not the punctuation. These used to assert
    // "What this report is." with a trailing period, which was really an
    // assertion that the copy is a bolded run-in paragraph — so turning the
    // four paragraphs into titled blocks broke a test that had no opinion about
    // any of that. Both headings must be present, and so must the sentence the
    // retired per-surface mark used to carry.
    expect(screen.getByRole("heading", { name: /what this report is/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /what it is not/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /how to use it/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /limits that apply to every figure/i })).toBeInTheDocument();
    const text = screen.getByTestId("report-disclosure").textContent ?? "";
    expect(text).toMatch(/not legal advice/i);
    // The cohort is a real figure or it is absent — never a placeholder.
    expect(text).toMatch(/n=42/);
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
