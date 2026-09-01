/**
 * Canonical score→color banding — single source of truth.
 *
 * Standing scale (OD-13, owner-decided 2026-08-31): GREEN good · YELLOW
 * middling · RED poor, for every score regardless of which direction the number
 * runs. Teal and gold are no longer standing colors — they keep their
 * non-standing jobs (verified/approved/live; draft/provisional/added-diff).
 *
 * These are TOKEN REFERENCES, not values. They used to be literal hex, which
 * gave the standing scale two sources of truth: theme.css (oklch, one value per
 * mode) and this file (hex, light-mode only). Every caller of scoreBandColor()
 * therefore rendered the LIGHT standing colour in dark mode — where the light
 * values measure 2.64–3.34:1 on the card and fail AA badly.
 *
 * A var() string works everywhere these are used: CSS properties, inline
 * `style`, and SVG `fill`/`stroke` attributes. The one place it does not is a
 * canvas 2D context, which resolves no custom properties — nothing here draws
 * to canvas, and check_colors.py keeps a literal from creeping back.
 */
export const STANDING_GOOD = "var(--standing-good)";
export const STANDING_MID = "var(--standing-mid)";
export const STANDING_BAD = "var(--standing-bad)";

export const SCORE_BAND_HIGH = 70;
export const SCORE_BAND_ELEVATED = 45;

/** EXPOSURE scores (higher = worse): ≥70 red · ≥45 yellow · below green. */
export function scoreBandColor(score: number): string {
  if (score >= SCORE_BAND_HIGH) return STANDING_BAD;      // high exposure
  if (score >= SCORE_BAND_ELEVATED) return STANDING_MID;  // elevated
  return STANDING_GOOD;                                   // lower exposure
}

/**
 * MATURITY scores (higher = better): color follows the canonical VICBNF
 * maturity bands so the color always agrees with the band label —
 * ≥75 green (Mature/Leading) · ≥60 yellow (Developing) · below red
 * (Lagging/Deficient). "Deficient" is never green. (design-system §2 v1.6)
 */
export function maturityBandColor(score: number): string {
  if (score >= 75) return STANDING_GOOD; // Mature / Leading
  if (score >= 60) return STANDING_MID;  // Developing
  return STANDING_BAD;                   // Lagging / Deficient
}

/** Neutral ink for metrics whose polarity is unknown — never a guessed judgement. */
export const NEUTRAL_SCORE_COLOR = "var(--foreground)";

/** Color a score by its own polarity; unknown polarity renders neutral. */
export function bandColor(score: number, polarity: MetricPolarity | undefined): string {
  if (polarity === "maturity") return maturityBandColor(score);
  if (polarity === "exposure") return scoreBandColor(score);
  return NEUTRAL_SCORE_COLOR;
}

/**
 * Per-metric polarity registry — derived from each formula's documented
 * meaning (intelligence-logic §7 / Methodology): maturity = higher is better,
 * exposure = higher is worse. Matches formula IDs and display names.
 * Unknown metrics return undefined → neutral color. Data/SME verify new rows
 * (design-system §2 v1.3 changelog carries the verification flag).
 */
const MATURITY_PATTERNS = /overall|maturity|transparency|percentile|reliability|clarity/i;
const EXPOSURE_PATTERNS = /exposure|risk|deviation|correlation|enforcement|sensitivity/i;
const FORMULA_POLARITY: Record<string, MetricPolarity> = {
  "F-001": "maturity",  // Source Reliability — higher is better
  "F-002": "exposure",  // Regulatory Exposure
  "F-003": "exposure",  // Benchmark Deviation — distance from top quartile
  "F-004": "exposure",  // Enforcement Correlation
  "F-005": "maturity",  // Disclosure Maturity
  "F-006": "maturity",  // Transparency
  "F-007": "maturity",  // AI Transparency Maturity
  "F-008": "exposure",  // Compound Risk
  "F-009": "exposure",  // Confidence Weighted (risk metric)
  "F-010": "maturity",  // Overall Privacy Intelligence — banded Leading…Deficient
  "F-011": "maturity",  // Benchmark Percentile — higher rank is better
};

export function metricPolarity(nameOrFormulaId: string): MetricPolarity | undefined {
  const byId = FORMULA_POLARITY[nameOrFormulaId.toUpperCase()];
  if (byId) return byId;
  if (MATURITY_PATTERNS.test(nameOrFormulaId)) return "maturity";
  if (EXPOSURE_PATTERNS.test(nameOrFormulaId)) return "exposure";
  return undefined;
}

/**
 * Cohort size below which benchmarking is labelled low-confidence.
 * OD-05: final cutoff pending data team — keep the constant, change the value.
 */
export const LOW_CONFIDENCE_COHORT_N = 10;

/**
 * VICBNF v2 spec maturity band labels (0-100 → Leading…Deficient).
 */
export function maturityBand(score: number): string {
  if (score >= 90) return "Leading";
  if (score >= 75) return "Mature";
  if (score >= 60) return "Developing";
  if (score >= 40) return "Lagging";
  return "Deficient";
}

/**
 * VICBNF v2 spec VCI band labels (0-100 → Very High…Very Low).
 */
export function vciBand(score: number): string {
  if (score >= 90) return "Very High";
  if (score >= 75) return "High";
  if (score >= 60) return "Moderate";
  if (score >= 40) return "Low";
  return "Very Low";
}

/**
 * Metric polarity — which direction counts as "better".
 * - "exposure": lower is better (all F-002…F-014 exposure/risk scores). Default.
 * - "maturity": higher is better (the quarterly Intelligence Indicators —
 *   Disclosure Maturity, AI Transparency, Consumer Rights Clarity).
 */
export type MetricPolarity = "exposure" | "maturity";

/**
 * Trend/delta coloring — by IMPROVEMENT, not direction (DDR-009).
 * Exposure scores read lower = better, so a falling score is teal (improving)
 * and a rising score is red (worsening). Maturity indices invert the mapping.
 * Arrows (▲/▼) still show direction; color carries the judgement.
 *
 * The `polarity` flag is required by design-system.md §2 and F12 AC-8 so the
 * quarterly Intelligence Indicators (maturity) and exposure scores can share
 * one coloring rule. Defaults to "exposure" — existing single-arg callers keep
 * their behavior unchanged.
 */
export function trendColor(delta: number, polarity: MetricPolarity = "exposure"): string {
  if (delta === 0) return "var(--muted-foreground)"; // no movement
  const improving = polarity === "maturity" ? delta > 0 : delta < 0;
  return improving ? STANDING_GOOD : STANDING_BAD;
}
