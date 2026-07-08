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
 * Trend/delta coloring — by IMPROVEMENT, not direction.
 * Exposure scores read lower = better, so a falling score is teal (improving)
 * and a rising score is red (worsening). Arrows (▲/▼) still show direction;
 * color carries the judgement.
 */
export function trendColor(delta: number): string {
  if (delta === 0) return "#8896A5"; // text-muted — no movement
  return delta < 0 ? "#55C7B3" : "#F87171";
}
