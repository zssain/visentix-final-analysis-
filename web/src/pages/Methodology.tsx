import { PageHeader } from "../components/PageHeader";
import "../components/furniture.css";

const FORMULAS = [
  { id: "F-001", name: "Source Reliability Score",       purpose: "Evaluates how authoritative, fresh, and complete the source record is." },
  { id: "F-002", name: "Regulatory Exposure Score",      purpose: "Weights jurisdiction importance against regulator priority and disclosure severity per domain." },
  { id: "F-003", name: "Benchmark Deviation Score",      purpose: "Quantifies how far the organisation's score is from the top quartile of its peer cohort." },
  { id: "F-004", name: "Enforcement Correlation Score",  purpose: "Measures overlap between the organisation's disclosure clauses and historical enforcement action patterns." },
  { id: "F-005", name: "Disclosure Maturity Score",      purpose: "Scores the proportion of required disclosure elements present versus the master element checklist." },
  { id: "F-006", name: "Transparency Score",             purpose: "Combines readability, clarity, and completeness indicators into a single transparency figure." },
  { id: "F-007", name: "AI Transparency Maturity",       purpose: "Evaluates how specifically the notice addresses automated and AI-driven decision-making." },
  { id: "F-008", name: "Compound Risk Score",            purpose: "Blends regulatory, disclosure, and enforcement dimensions into one compound risk indicator." },
  { id: "F-009", name: "Confidence Weighted Score",      purpose: "Adjusts risk metrics downward when source reliability is low." },
  { id: "F-010", name: "Overall Privacy Intelligence Score", purpose: "Weighted combination of all six risk dimensions into the headline score." },
  { id: "F-011", name: "Benchmark Percentile",           purpose: "The organisation's rank relative to its weighted peer cohort." },
  { id: "F-012", name: "Trend Delta",                    purpose: "The temporal shift in overall score between the current and prior snapshot. Reports 'no prior history' on first assessment." },
  { id: "F-013", name: "Alert Escalation",               purpose: "Triggers a monitoring alert when scores fall below a threshold or significant notice changes are detected." },
  { id: "F-014", name: "Report Confidence Index (VCI)",  purpose: "Refined confidence rating that accounts for cohort size, source quality, and classification certainty." },
];

const GUARDRAIL_TERMS = [
  "violation", "violates", "illegal", "unlawful",
  "non-compliant", "breach of law", "guilty", "liable",
];

const SME_STEPS = [
  { step: "1", label: "Report generated", detail: "Scores computed, narrative drafted in house voice." },
  { step: "2", label: "SME review queue", detail: "Each finding is presented to a subject-matter expert." },
  { step: "3", label: "Confirm / Edit / Dismiss", detail: "SME confirms accuracy, edits language, or dismisses." },
  { step: "4", label: "De-identification check", detail: "Exemplar text is scanned and redacted before use." },
  { step: "5", label: "Approval", detail: "Approved report moves from draft to client-visible." },
];

export function Methodology() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <PageHeader
        eyebrow="Methodology"
        title="How Visentix Works"
        description="Privacy intelligence built on deterministic formulas, human expert review, and honest benchmarking. Every figure is traceable. Every report is reproducible."
      />

      {/* The formulas */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700, color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 6 }}>
          14 Versioned Formulas
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", marginBottom: 20 }}>
          Every score is the output of one of these formulas. Formula IDs are published in every report and lineage drawer.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 0, border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
          {FORMULAS.map((f, i) => (
            <div key={f.id} style={{
              display: "flex", gap: 16, padding: "12px 16px", alignItems: "flex-start",
              background: i % 2 === 0 ? "white" : "var(--soft-white)",
              borderBottom: i < FORMULAS.length - 1 ? "1px solid var(--border)" : "none",
            }}>
              <span style={{
                background: "var(--navy)", color: "white",
                fontFamily: "var(--font-data)", fontSize: "0.72rem", fontWeight: 700,
                padding: "3px 8px", borderRadius: 4, flexShrink: 0, marginTop: 2,
              }}>{f.id}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "var(--navy)", marginBottom: 2 }}>{f.name}</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{f.purpose}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Intelligence, not verdicts */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700, color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 6 }}>
          Intelligence, Not Legal Verdicts
        </h2>
        <div style={{
          borderLeft: "3px solid var(--gold)", paddingLeft: 20, marginBottom: 16,
        }}>
          <p style={{ fontFamily: "var(--font-display)", fontStyle: "italic", fontSize: "1.05rem", color: "var(--navy)", lineHeight: 1.6, marginBottom: 8 }}>
            Visentix answers "compared to whom, with what exposure, at what confidence."
            It never answers "is this legal?"
          </p>
          <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>
            A phrasing guardrail runs at report-draft time and hard-blocks any attempt to output legal-verdict language.
            Reports are written in exposure, maturity, likelihood, benchmark, and confidence terms only.
          </p>
        </div>
        <div style={{ background: "var(--soft-white)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "14px 16px" }}>
          <div className="section-label" style={{ marginBottom: 10 }}>Guardrail — blocked terms</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {GUARDRAIL_TERMS.map(t => (
              <span key={t} style={{
                padding: "3px 10px", borderRadius: 4,
                background: "rgba(248,113,113,0.08)",
                border: "1px solid rgba(248,113,113,0.25)",
                color: "#b91c1c", fontSize: "0.78rem", fontWeight: 600,
                textDecoration: "line-through", opacity: 0.7,
              }}>{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* SME review gate */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700, color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 6 }}>
          Human Expert Review Gate
        </h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", marginBottom: 20, lineHeight: 1.6 }}>
          Every report passes through a subject-matter expert before becoming client-visible.
          Every review decision is captured as a training label for model improvement.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }} className="stripe-timeline">
          {SME_STEPS.map((s, i) => (
            <div key={s.step} className={`stripe-timeline-item ${i === 0 ? "done" : i === 1 ? "active" : ""}`}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: "50%",
                  background: i < 2 ? "var(--navy)" : "var(--border)",
                  color: "white", display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.75rem", fontWeight: 700, flexShrink: 0,
                }}>{s.step}</div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "var(--navy)" }}>{s.label}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 2 }}>{s.detail}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Reproducibility */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700, color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 6 }}>
          Reproducibility & Lineage
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {[
            { title: "Frozen Snapshots",  body: "Reports are frozen at publication. Pulling the same snapshot ID twice produces byte-identical output. Re-scoring creates a new versioned snapshot; history is never overwritten." },
            { title: "No Score Without Lineage",    body: "Every score stores its formula version, input references, VCI confidence, and generation timestamp. Click any score in a report to see the full lineage." },
            { title: "Honest Benchmarking",    body: "Cohort sizes are always reported exactly, live-queried with their as-of date. Low-confidence labels are attached when cohort size is small. No inflated numbers." },
            { title: "Deterministic Narrative",     body: "Advisor Note prose is frozen into the snapshot. It is never regenerated at render time, eliminating LLM non-determinism from the final deliverable." },
          ].map(card => (
            <div key={card.title} className="card" style={{ padding: "16px 18px" }}>
              <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)", marginBottom: 6 }}>{card.title}</div>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>{card.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* About */}
      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 700, color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 10 }}>
          About Visentix
        </h2>
        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.75 }}>
          Visentix is a privacy intelligence platform built by SOLRAC. It turns public privacy notices into
          benchmark-driven intelligence for regulators, legal officers, and privacy advisors — the people who
          need to understand where an organisation stands relative to its peers, with the evidence to defend that view.
        </p>
      </section>

    </div>
  );
}
