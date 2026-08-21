import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

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
  const findingEvidence = (content.finding_evidence as {
    id?: string; formula_version?: string; confidence?: string | number;
    evidence?: { clause_id?: string; section_reference?: string; excerpt?: string; source_reference?: string }[];
  }[] | undefined) ?? [];

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
          { key: "Formula Version",     val: formulaVer ?? "Not recorded" },
          { key: "Frozen",              val: frozenDate },
          { key: "Assessment ID",       val: assessmentId },
          { key: "Formulas Applied",    val: formulaIds.length ? formulaIds.join("  ·  ") : "Not recorded" },
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

      <div style={{ marginBottom: 16, fontSize: "0.82rem", color: "var(--text-secondary)" }}>
        Guardrail: <strong>{guardrail?.status ?? "not recorded"}</strong> · Template-token gate: <strong>{templateTokens?.status ?? "not recorded"}</strong> · Clause read agreement: <strong>{extraction?.status ?? "not recorded"}</strong>
      </div>

      <h3>Finding evidence lineage</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 16 }}>
        <thead><tr><th>Finding</th><th>Clause / section</th><th>Excerpt</th><th>Source</th><th>Formula</th><th>Confidence</th></tr></thead>
        <tbody>
          {findingEvidence.length ? findingEvidence.flatMap(f => (f.evidence ?? []).length ? (f.evidence ?? []).map((ev, i) => (
            <tr key={`${f.id}-${i}`}><td>{f.id}</td><td>{ev.clause_id ?? "Not recorded"}<br />{ev.section_reference ?? "Not recorded"}</td><td>{ev.excerpt ?? "Not recorded"}</td><td>{ev.source_reference ?? "Not recorded"}</td><td>{f.formula_version ?? "Not recorded"}</td><td>{f.confidence ?? "Not recorded"}</td></tr>
          )) : [<tr key={`${f.id}-absent`}><td>{f.id}</td><td colSpan={5}>No stored clause reference for this finding.</td></tr>]) : <tr><td colSpan={6}>No finding evidence is recorded.</td></tr>}
        </tbody>
      </table>

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
