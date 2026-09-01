/**
 * THE reader-facing label registry.
 *
 * The same transformation — `value.replace(/_/g, " ")` — was written inline at
 * 20 call sites, each free to drift, and several enums rendered completely raw:
 * a finding's severity showed as "high", not "High exposure". A reader saw the
 * database's vocabulary, and saw it worded differently on different screens.
 *
 * Two rules:
 *
 *  1. **A reader never sees a raw enum.** Every value that reaches the screen
 *     passes through here.
 *  2. **An unknown value stays visibly unknown.** Nothing here invents a label
 *     for a value it does not recognise — it title-cases the raw string so the
 *     gap is obvious rather than papered over with a plausible word
 *     (Hard Rule 7). Silent prettification is how an unmapped enum ships.
 *
 * Vocabulary is exposure/maturity language, never legal-verdict language
 * (Hard Rule 1), and carries no house acronyms (design-system §2).
 */

/** Last resort: `not_yet_reviewed` → "Not yet reviewed". Never a guess at meaning. */
export function humanize(value: string): string {
  if (!value) return "Not recorded";
  const s = value.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ── Severity — a standing, in exposure language ────────────────────────────
const SEVERITY: Record<string, string> = {
  critical: "High exposure",
  high:     "High exposure",
  elevated: "Elevated exposure",
  medium:   "Elevated exposure",
  moderate: "Moderate exposure",
  low:      "Lower exposure",
};
export function severityLabel(v: string | null | undefined): string {
  if (!v) return "Not recorded";
  return SEVERITY[v.toLowerCase()] ?? humanize(v);
}

// ── Job / task status ──────────────────────────────────────────────────────
const STATUS: Record<string, string> = {
  queued: "Queued", running: "Running", complete: "Complete", failed: "Failed",
  succeeded: "Succeeded", pending: "Pending", draft: "Draft",
  approved: "Approved", rejected: "Not approved",
  in_review: "In review", reviewed: "Reviewed",
};
export function statusLabel(v: string | null | undefined): string {
  if (!v) return "Not recorded";
  return STATUS[v.toLowerCase()] ?? humanize(v);
}

// ── Notice type ────────────────────────────────────────────────────────────
const NOTICE_TYPE: Record<string, string> = {
  live_assessment: "Live assessment",
  reference_corpus: "Reference corpus",
  uploaded: "Uploaded",
};
export function noticeTypeLabel(v: string | null | undefined): string {
  if (!v) return "Not recorded";
  return NOTICE_TYPE[v.toLowerCase()] ?? humanize(v);
}

// ── Review action ──────────────────────────────────────────────────────────
const ACTION: Record<string, string> = {
  confirm: "Confirmed", edit: "Edited", dismiss: "Dismissed",
};
export function actionLabel(v: string | null | undefined): string {
  if (!v) return "Not recorded";
  return ACTION[v.toLowerCase()] ?? humanize(v);
}

export { domainLabel } from "./domainLabels";
