import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

// [MOCK M-09] snapshot_id and formula_version read from content
// real: report_snapshot.id and frozen_at from Supabase, threaded through the API response
export function Traceability({ content }: { content: ReportSection["content"] }) {
  const snapshotId  = (content.snapshot_id     as string | undefined) ?? "S-0000";
  const formulaVer  = (content.formula_version as string | undefined) ?? "v1.0";
  const frozenDate  = (content.date            as string | undefined) ?? "—";
  const assessmentId= (content.assessment_id   as string | undefined) ?? "—";
  const isDraft     = (content.is_draft        as boolean | undefined) ?? false;
  const note        = content.note             as string | undefined;

  const formulaIds  = (content.formula_ids as string[] | undefined) ?? [
    "F-001","F-002","F-003","F-004","F-005","F-006",
    "F-007","F-008","F-009","F-010","F-011","F-012","F-013","F-014",
  ];

  return (
    <div data-testid="section-11" className="report-section">
      <h2>11. Source Traceability</h2>

      <ProvenanceRibbon
        snapshotId={snapshotId}
        formulaVersion={formulaVer}
        frozenDate={frozenDate}
        status={isDraft ? "draft" : "approved"}
      />

      {note && (
        <p style={{ color: "var(--text-secondary)", marginBottom: 16, fontSize: "0.88rem" }}>{note}</p>
      )}

      {/* Traceability table */}
      <div style={{
        background: "var(--soft-white)", border: "1px solid var(--border)",
        borderRadius: "var(--radius)", overflow: "hidden", marginBottom: 16,
      }}>
        {[
          { key: "Snapshot ID",         val: snapshotId },
          { key: "Formula Version",     val: formulaVer },
          { key: "Frozen",              val: frozenDate },
          { key: "Assessment ID",       val: assessmentId },
          { key: "Formulas Applied",    val: formulaIds.join("  ·  ") },
        ].map(({ key, val }, i) => (
          <div key={i} style={{
            display: "flex", gap: 16, padding: "10px 16px",
            borderBottom: i < 4 ? "1px solid var(--border)" : "none",
            background: i % 2 === 0 ? "var(--soft-white)" : "white",
          }}>
            <span style={{
              width: 160, flexShrink: 0,
              fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.07em", color: "var(--text-muted)",
            }}>{key}</span>
            <span style={{
              fontFamily: "var(--font-data)", fontSize: "0.82rem",
              fontVariantNumeric: "tabular-nums", color: "var(--navy)",
              wordBreak: "break-all",
            }}>{val}</span>
          </div>
        ))}
      </div>

      <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
        This report was generated from a frozen snapshot of all scores, lineage references, and narrative text.
        Re-pulling this report from the same snapshot ID will produce byte-identical output.
        Re-scoring against new data creates a new versioned snapshot and preserves this record unchanged.
      </p>

      <div style={{ marginTop: 12 }}>
        <IntelligenceMark />
      </div>
    </div>
  );
}
