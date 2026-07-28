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
import { createElement } from "react";
import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Recommendations } from "../report/sections/Recommendations";
import { RiskReduction } from "../report/sections/RiskReduction";

import {
  trendColor, scoreBandColor, maturityBandColor, bandColor,
  metricPolarity, maturityBand, NEUTRAL_SCORE_COLOR,
} from "../lib/scoreBands";
import * as quarterlyMock from "../pages/quarterly/mockData";
// partner (F11 M-19–M-22) mock removed — replaced by the real F20 partner
// portal; its feed vocabulary is guarded by backend test_f20_partner.py.
// bulk (F12 M-23/M-24) mock removed — replaced by the real F19 bulk-screening
// surface; its export vocabulary is guarded by the backend test_f19_bulk.py.
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

// ── Report-section static copy — banned-term filter (WS4) ────
// Renders each section with clean data, so any banned term in the output can
// only come from the component's own hardcoded copy. Covers the two sections
// (Recommendations, RiskReduction) whose static prose had no automated guard.

describe("banned-term filter over report-section static copy (Hard Rule 1)", () => {
  afterEach(cleanup);

  const SECTIONS: Record<string, () => ReturnType<typeof createElement>> = {
    "Recommendations.tsx": () => createElement(Recommendations, {
      content: {
        recommendations: [
          { severity: "high", code: "SH-002", title: "Clarify sharing",
            prose: "Strengthen data-sharing disclosures to reduce exposure indicators." },
          { severity: "medium", code: "RT-003", title: "Define retention",
            prose: "Add explicit retention periods per data category." },
        ],
      },
    }),
    "RiskReduction.tsx": () => createElement(RiskReduction, {
      content: {
        high_count: 2, medium_count: 1,
        priorities: [{ code: "SH-002", domain: "data_sharing", severity: "high", score: 60 }],
        prose: "Prioritise the highest-exposure domains first.",
      },
    }),
  };

  for (const [name, factory] of Object.entries(SECTIONS)) {
    it(`${name} static copy contains no verdict vocabulary`, () => {
      const { container } = render(factory());
      const text = (container.textContent ?? "").toLowerCase();
      const found = BANNED_TERMS.filter(term =>
        new RegExp(`\\b${escapeRe(term)}\\b`, "i").test(text));
      expect(found).toEqual([]);
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

// ── Polarity-aware score coloring (design-system §2 v1.3) ─────
// Color always carries the same judgement: teal good, gold middling,
// red poor — whichever direction the metric runs.

describe("polarity-aware score coloring — color agrees with meaning", () => {
  const TEAL = "#55C7B3", GOLD = "#C8A46A", RED = "#F87171";

  it("maturity scale: color always agrees with the maturity band label", () => {
    expect(maturityBand(34.9)).toBe("Deficient");
    expect(maturityBandColor(34.9)).toBe(RED);      // Deficient is never teal
    expect(maturityBand(8.8)).toBe("Deficient");
    expect(maturityBandColor(8.8)).toBe(RED);       // Transparency 8.8 is not "good"
    expect(maturityBand(62.3)).toBe("Developing");
    expect(maturityBandColor(62.3)).toBe(GOLD);
    expect(maturityBand(80)).toBe("Mature");
    expect(maturityBandColor(80)).toBe(TEAL);
  });

  it("exposure scale unchanged: high exposure red, low exposure teal", () => {
    expect(scoreBandColor(82.2)).toBe(RED);
    expect(scoreBandColor(50)).toBe(GOLD);
    expect(scoreBandColor(17.1)).toBe(TEAL);
  });

  it("bandColor dispatches by polarity; unknown polarity is neutral, never a guess", () => {
    expect(bandColor(34.9, "maturity")).toBe(RED);
    expect(bandColor(34.9, "exposure")).toBe(TEAL);
    expect(bandColor(34.9, undefined)).toBe(NEUTRAL_SCORE_COLOR);
  });

  it("metric polarity registry classifies the screenshot's metrics correctly", () => {
    expect(metricPolarity("Regulatory Exposure")).toBe("exposure");
    expect(metricPolarity("Compound Risk")).toBe("exposure");
    expect(metricPolarity("Enforcement Correlation")).toBe("exposure");
    expect(metricPolarity("Benchmark Deviation")).toBe("exposure");
    expect(metricPolarity("Disclosure Maturity")).toBe("maturity");
    expect(metricPolarity("Transparency")).toBe("maturity");
    expect(metricPolarity("AI Transparency")).toBe("maturity");
    expect(metricPolarity("Benchmark Percentile")).toBe("maturity");
    expect(metricPolarity("F-010")).toBe("maturity");
    expect(metricPolarity("F-002")).toBe("exposure");
    expect(metricPolarity("something-unrecognized")).toBeUndefined();
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
