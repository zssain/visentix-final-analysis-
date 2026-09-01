import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { Badge } from "@/components/ui/badge";

interface Rec {
  severity: string; code: string; title: string; prose: string;
  basis_label?: string; source_note?: string;
  evidence?: { clause_id?: string; section_reference?: string; excerpt?: string }[];
}

// Guardrail-compliant severity labels — exposure language, never legal verdict
// language (Hard Rule 1).
const SEVERITY_LABEL: Record<string, string> = {
  high:     "High Exposure",
  elevated: "Elevated Exposure",
  moderate: "Moderate Exposure",
  low:      "Lower Exposure",
};

/** Severity IS a standing, so it uses the traffic-light scale (OD-13).
 *
 *  It previously used red/gold/blue/teal — mixing the standing scale with the
 *  non-standing status colours, so "moderate" was rendered in the same blue as
 *  an interactive element and "low" in the teal that means *verified*.
 *
 *  Four labels map onto three colours, so "elevated" and "moderate" share the
 *  middle. That is deliberate: colour carries the band, the LABEL carries the
 *  distinction, and no meaning here is ever colour-alone. */
const SEVERITY_VARIANT: Record<string, "standing-bad" | "standing-mid" | "standing-good"> = {
  high:     "standing-bad",
  elevated: "standing-mid",
  moderate: "standing-mid",
  low:      "standing-good",
};

const SEVERITY_RULE: Record<string, string> = {
  high:     "var(--standing-bad)",
  elevated: "var(--standing-mid)",
  moderate: "var(--standing-mid)",
  low:      "var(--standing-good)",
};

export function Recommendations({ content }: { content: ReportSection["content"] }) {
  const recs = (content.recommendations as Rec[]) ?? [];

  return (
    <div data-testid="section-9" className="report-section">
      <SectionHeading n={9} title="Strategic Recommendations" />
      <p className="mb-4 max-w-prose text-sm text-muted-foreground">
        Recommendations are ordered by exposure level. They describe disclosure gaps and maturity
        improvements — not legal requirements.
      </p>

      {recs.length === 0 ? (
        <div className="rounded-lg border bg-muted/40 px-4 py-4 text-sm text-muted-foreground">
          No recommendations to display at this time.
        </div>
      ) : (
        /* Each recommendation is a card, not a bordered paragraph.
           The old layout gave the title and the body the same size and put the
           body in muted ink, so the eye found the ORDER of the list but not the
           point of any entry. Now: a rank numeral to read down, the title at
           full contrast one step up in size, the body in body ink, and the
           provenance in its own quiet footer so absence stays readable without
           competing with the recommendation. */
        <ol className="flex flex-col gap-4">
          {recs.map((r, i) => {
            const sev = r.severity.toLowerCase();
            const rule = SEVERITY_RULE[sev] ?? "var(--border)";
            return (
              <li
                key={i}
                className="overflow-hidden rounded-lg border bg-card"
                data-testid={`recommendation-${i}`}
              >
                {/* Header band: rank, code, standing. The severity rail runs the
                    full height of the card so the standing is legible from the
                    page margin, not only from the badge. */}
                <div className="flex items-start gap-3 border-l-[4px] px-4 py-3" style={{ borderLeftColor: rule }}>
                  <span
                    className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted font-data text-xs font-bold tabular-nums text-muted-foreground"
                    aria-hidden="true"
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="font-data">{r.code}</Badge>
                      <Badge variant={SEVERITY_VARIANT[sev] ?? "secondary"}>
                        {SEVERITY_LABEL[sev] ?? r.severity}
                      </Badge>
                    </div>
                    {r.title && (
                      <h4 className="m-0 text-base font-semibold leading-snug text-foreground">
                        {r.title}
                      </h4>
                    )}
                  </div>
                </div>

                <div className="border-l-[4px] px-4 pb-4" style={{ borderLeftColor: rule }}>
                  <p className="m-0 max-w-prose text-sm leading-relaxed text-foreground/85">
                    {r.prose}
                  </p>
                </div>

                {/* Provenance lines. Each states honest absence in its own words:
                    "no basis recorded" and "no evidence recorded" are different
                    claims and must never collapse into one. Separated from the
                    recommendation so a reader can see at a glance whether one is
                    backed by evidence — that is the point of printing it. */}
                <dl className="flex flex-col gap-1 border-t bg-muted/40 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
                  <div>
                    <dt className="inline font-semibold text-foreground/70">Basis: </dt>
                    <dd className="inline">{r.basis_label ?? "Basis not recorded"}</dd>
                  </div>
                  <div>
                    <dt className="inline font-semibold text-foreground/70">Notice evidence: </dt>
                    <dd className="inline">
                      {(r.evidence ?? []).length > 0
                        ? <>
                            {r.evidence?.[0]?.section_reference ?? r.evidence?.[0]?.clause_id ?? "Stored clause"}
                            {" — "}
                            {r.evidence?.[0]?.excerpt ?? "Excerpt not recorded"}
                          </>
                        : "No triggering notice evidence is recorded."}
                    </dd>
                  </div>
                  <div>
                    {r.source_note
                      ? <><dt className="inline font-semibold text-foreground/70">Authored source note: </dt><dd className="inline">{r.source_note}</dd></>
                      : <dd className="inline">No authored source citation is recorded.</dd>}
                  </div>
                </dl>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
