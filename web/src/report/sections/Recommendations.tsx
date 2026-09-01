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
        <ol className="flex flex-col gap-3">
          {recs.map((r, i) => {
            const sev = r.severity.toLowerCase();
            return (
              <li
                key={i}
                className="border-l-[3px] py-1 pl-4"
                style={{ borderColor: SEVERITY_RULE[sev] ?? "var(--border)" }}
              >
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge className="font-data">{r.code}</Badge>
                  <Badge variant={SEVERITY_VARIANT[sev] ?? "secondary"}>
                    {SEVERITY_LABEL[sev] ?? r.severity}
                  </Badge>
                </div>

                {r.title && <div className="mb-1 text-sm font-semibold">{r.title}</div>}

                <p className="max-w-prose text-sm leading-relaxed text-muted-foreground">{r.prose}</p>

                {/* Provenance lines. Each states honest absence in its own words:
                    "no basis recorded" and "no evidence recorded" are different
                    claims and must never collapse into one. */}
                <dl className="mt-1.5 flex flex-col gap-0.5 text-xs text-muted-foreground">
                  <div>
                    <dt className="inline font-semibold">Basis: </dt>
                    <dd className="inline">{r.basis_label ?? "Basis not recorded"}</dd>
                  </div>
                  <div>
                    <dt className="inline font-semibold">Notice evidence: </dt>
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
                      ? <><dt className="inline font-semibold">Authored source note: </dt><dd className="inline">{r.source_note}</dd></>
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
