/**
 * Canonical score→color banding — single source of truth.
 * Red is reserved for high exposure only (design token rule, UI_SPEC §0).
 * Hex literals mirror the token palette so the same values work in CSS
 * and in SVG/Recharts `fill` attributes.
 */
export const SCORE_BAND_HIGH = 70;
export const SCORE_BAND_ELEVATED = 45;

export function scoreBandColor(score: number): string {
  if (score >= SCORE_BAND_HIGH) return "#F87171";     // red — high exposure (only legitimate use)
  if (score >= SCORE_BAND_ELEVATED) return "#C8A46A"; // gold — elevated
  return "#55C7B3";                                   // teal — lower exposure
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
  if (delta === 0) return "#8896A5"; // text-muted — no movement
  const improving = polarity === "maturity" ? delta > 0 : delta < 0;
  return improving ? "#55C7B3" : "#F87171";
}
