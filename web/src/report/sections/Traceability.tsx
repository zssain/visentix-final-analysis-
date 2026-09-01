import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { SourceSummary } from "./SourceSummary";
import { cn } from "@/lib/utils";

export function Traceability({ content }: { content: ReportSection["content"] }) {
  const snapshotId  = (content.snapshot_id     as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const formulaVer  = content.formula_version as string | undefined;
  const frozenDate  = (content.date            as string | undefined) ?? "—";
  const assessmentId= (content.assessment_id   as string | undefined) ?? "—";
  const isDraft     = (content.is_draft        as boolean | undefined) ?? false;
  const note        = content.note             as string | undefined;

  const formulaIds  = (content.formula_versions_used as string[] | undefined) ?? [];
  const guardrail = content.guardrail as { status?: string } | undefined;
  const templateTokens = content.template_tokens as { status?: string } | undefined;
  const extraction = content.extraction_quality as { status?: string } | undefined;
  const sourceSummary = content.source_summary as {
    drivers?: { judgment?: string; rests_on?: string; strength?: string; why?: string }[];
    strengths?: string[];
    limitations?: string[];
  } | undefined;

  const findingEvidence = (content.finding_evidence as {
    id?: string; formula_version?: string; confidence?: string | number;
    evidence?: { clause_id?: string; section_reference?: string; excerpt?: string; source_reference?: string }[];
  }[] | undefined) ?? [];

  return (
    <div data-testid="section-11" className="report-section">
      <SectionHeading n={11} title="Source Traceability" />

      <ProvenanceRibbon
        snapshotId={snapshotId}
        formulaVersion={formulaVer}
        frozenDate={frozenDate}
        status={isDraft ? "draft" : "approved"}
      />

      {note && (
        <p className="mb-4 text-sm text-muted-foreground">{note}</p>
      )}

      <SourceSummary summary={sourceSummary} />

      {/* The identity table.
          Its zebra striping used to set a literal white on every other row from
          an inline style, so in dark mode the panel struck five blinding bands
          across the card and painted var(--navy) text — which the token bridge
          maps to the light-on-dark --primary — on top of them. Unreadable.
          Everything here is tokens now, and the tint inverts with the theme.

          check_colors.py did not catch it: its named-colour rule ran over
          stylesheets only, because in TSX a bare `teal` is usually a variable.
          A QUOTED one never is, so the guard now checks that in TSX too. */}
      <dl className="mb-4 overflow-hidden rounded-lg border" data-testid="traceability-table">
        {[
          { key: "Snapshot ID",      val: snapshotId },
          { key: "Formula Version",  val: formulaVer ?? "Not recorded" },
          { key: "Frozen",           val: frozenDate },
          { key: "Assessment ID",    val: assessmentId },
          { key: "Formulas Applied", val: formulaIds.length ? formulaIds.join("  ·  ") : "Not recorded" },
        ].map(({ key, val }, i, arr) => (
          <div
            key={key}
            className={cn(
              "flex flex-col gap-1 px-4 py-2.5 sm:flex-row sm:items-baseline sm:gap-4",
              i < arr.length - 1 && "border-b",
              i % 2 === 1 && "bg-muted/40",
            )}
          >
            <dt className="w-44 shrink-0 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {key}
            </dt>
            <dd className="m-0 min-w-0 break-all font-data text-[0.82rem] tabular-nums text-foreground">
              {val}
            </dd>
          </div>
        ))}
      </dl>

      {/* Gate results. Three separate claims, so three separate rows — run
          together on one line they read as a single verdict, and "not recorded"
          three times looked like one repeated word rather than three gates that
          each produced nothing. */}
      <div className="mb-5 grid gap-2 sm:grid-cols-3">
        {[
          { label: "Guardrail",           status: guardrail?.status },
          { label: "Template-token gate", status: templateTokens?.status },
          { label: "Clause read agreement", status: extraction?.status },
        ].map(({ label, status }) => (
          <div key={label} className="rounded-lg border px-3 py-2.5">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className={cn(
              "mt-0.5 text-sm font-semibold",
              status ? "text-foreground" : "text-muted-foreground italic",
            )}>
              {status ?? "Not recorded"}
            </div>
          </div>
        ))}
      </div>

      <h3 className="report-subhead">Finding evidence lineage</h3>
      <div className="mb-4 overflow-x-auto rounded-lg border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left">
              {["Finding", "Clause / section", "Excerpt", "Source", "Formula", "Confidence"].map(h => (
                <th key={h} className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {findingEvidence.length
              ? findingEvidence.flatMap(f => (f.evidence ?? []).length
                  ? (f.evidence ?? []).map((ev, i) => (
                      <tr key={`${f.id}-${i}`} className="border-b last:border-0 align-top">
                        <td className="px-3 py-2 font-data text-xs">{f.id}</td>
                        <td className="px-3 py-2 text-xs">
                          {ev.clause_id ?? "Not recorded"}
                          <div className="text-muted-foreground">{ev.section_reference ?? "Not recorded"}</div>
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">{ev.excerpt ?? "Not recorded"}</td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">{ev.source_reference ?? "Not recorded"}</td>
                        <td className="px-3 py-2 font-data text-xs">{f.formula_version ?? "Not recorded"}</td>
                        <td className="px-3 py-2 font-data text-xs tabular-nums">{f.confidence ?? "Not recorded"}</td>
                      </tr>
                    ))
                  : [(
                      <tr key={`${f.id}-absent`} className="border-b last:border-0">
                        <td className="px-3 py-2 font-data text-xs">{f.id}</td>
                        <td className="px-3 py-2 text-xs text-muted-foreground" colSpan={5}>
                          No stored clause reference for this finding.
                        </td>
                      </tr>
                    )])
              : (
                <tr>
                  <td className="px-3 py-6 text-center text-sm text-muted-foreground" colSpan={6}>
                    No finding evidence is recorded.
                  </td>
                </tr>
              )}
          </tbody>
        </table>
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        This report was generated from a frozen snapshot of all scores, lineage references, and narrative text.
        Re-pulling this report from the same snapshot ID will produce byte-identical output.
        Re-scoring against new data creates a new versioned snapshot and preserves this record unchanged.
      </p>

    </div>
  );
}
