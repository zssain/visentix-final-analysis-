/**
 * Guardrail tests over the UI-first mock datasets (audit 2026-07-16).
 *
 * These implement the unit tests the feature specs promise:
 *  - F12 AC-8  trendColor per-metric polarity
 *  - F13 AC-4  crosswalk copy passes the banned-term filter
 *  - F14 AC-2  rewrite patterns pass the banned-term filter
 *  - F14 AC-3  rewrite patterns contain no obligation framing
 *  - F15 AC-1  trust-center copy passes the banned-term filter
 *  - F15 AC-2  trust-center copy contains no security jargon / attack-class names
 *  - F16 AC-2  vendor summaries pass the banned-term filter
 *
 * The banned-term list is read from scripts/data/banned_terms.txt — the single
 * enforced list (spec-guard uses the same file) — so a term added there is
 * automatically enforced here too.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { describe, expect, it } from "vitest";

import { trendColor } from "../lib/scoreBands";
import * as quarterlyMock from "../pages/quarterly/mockData";
import * as partnerMock from "../pages/partner/mockData";
import * as bulkMock from "../pages/bulk/mockData";
import * as crosswalkMock from "../pages/crosswalk/mockData";
import * as rewriteMock from "../pages/rewrite/mockData";
import * as trustMock from "../pages/trust/mockData";
import * as vendorsMock from "../pages/vendors/mockData";

// ── Banned-term machinery ─────────────────────────────────────

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const BANNED_TERMS = readFileSync(resolve(repoRoot, "scripts/data/banned_terms.txt"), "utf-8")
  .split("\n")
  .map(l => l.trim())
  .filter(l => l && !l.startsWith("#"));

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** All banned terms found in a blob of display data (word-bounded, case-insensitive). */
function bannedTermsIn(data: unknown): string[] {
  const blob = JSON.stringify(data) ?? "";
  return BANNED_TERMS.filter(term =>
    new RegExp(`\\b${escapeRe(term)}\\b`, "i").test(blob));
}

const MOCK_MODULES: Record<string, unknown> = {
  "quarterly (F12, M-15–M-18)": { ...quarterlyMock },
  "partner (F11, M-19–M-22)": { ...partnerMock },
  "bulk (F12, M-23–M-24)": { ...bulkMock },
  "crosswalk (F13, M-25)": { ...crosswalkMock },
  "rewrite (F14, M-26)": { ...rewriteMock },
  "trust (F15, M-27)": { ...trustMock },
  "vendors (F16, M-28)": { ...vendorsMock },
};

describe("banned-term filter over every UI-first mock dataset (Hard Rule 1)", () => {
  it("loads a non-empty banned-term list from scripts/data", () => {
    expect(BANNED_TERMS.length).toBeGreaterThan(5);
  });

  for (const [name, module_] of Object.entries(MOCK_MODULES)) {
    it(`${name} contains no verdict vocabulary`, () => {
      expect(bannedTermsIn(module_)).toEqual([]);
    });
  }
});

// ── F14 AC-3: no obligation framing in rewrite patterns ──────

describe("F14 AC-3 — rewrite patterns avoid obligation framing", () => {
  const OBLIGATION = /\b(must|shall|required to|to comply|obligated to)\b/i;

  for (const p of rewriteMock.PROMPTS) {
    it(`${p.domainId} pattern + rationale are non-obligation`, () => {
      expect(p.pattern).not.toMatch(OBLIGATION);
      expect(p.rationale).not.toMatch(OBLIGATION);
    });
  }
});

// ── F15 AC-2: no security jargon on the public Trust Center ──

describe("F15 AC-2 — trust-center copy is register-appropriate (Hard Rule 9)", () => {
  const JARGON = /\b(SSRF|XSS|CSRF|RCE|CVE|OWASP|SQL injection|penetration test|pentest|exfiltration|attack vector)\b/i;

  it("contains no attack-class names or security jargon", () => {
    expect(JSON.stringify({ ...trustMock })).not.toMatch(JARGON);
  });
});

// ── F12 AC-8: trendColor per-metric polarity ──────────────────

describe("F12 AC-8 — trendColor polarity (DDR-009 + design-system §2)", () => {
  const TEAL = "#55C7B3", RED = "#F87171", MUTED = "#8896A5";

  it("exposure: falling = improving (teal), rising = worsening (red)", () => {
    expect(trendColor(-2.5, "exposure")).toBe(TEAL);
    expect(trendColor(+2.5, "exposure")).toBe(RED);
  });

  it("maturity: rising = improving (teal), falling = worsening (red)", () => {
    expect(trendColor(+2.5, "maturity")).toBe(TEAL);
    expect(trendColor(-2.5, "maturity")).toBe(RED);
  });

  it("zero delta is neutral regardless of polarity", () => {
    expect(trendColor(0, "exposure")).toBe(MUTED);
    expect(trendColor(0, "maturity")).toBe(MUTED);
  });

  it("defaults to exposure polarity — existing callers keep their behavior", () => {
    expect(trendColor(-1)).toBe(trendColor(-1, "exposure"));
    expect(trendColor(+1)).toBe(trendColor(+1, "exposure"));
  });
});

// ── F15 AC-3: no trust metric renders without a source note ──

describe("F15 AC-3 — every trust metric carries a source note", () => {
  for (const m of trustMock.TRUST_METRICS) {
    it(`"${m.label}" has a non-empty source note`, () => {
      expect(m.sourceNote.trim().length).toBeGreaterThan(0);
    });
  }
});
