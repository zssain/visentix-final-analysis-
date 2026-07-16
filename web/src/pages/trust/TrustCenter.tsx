/**
 * F15 — Public Trust Center · UI (public, trust metrics mocked M-27).
 *
 * A no-login page that states what Visentix claims (and doesn't), how customer
 * data is handled, how the intelligence is made reproducible, and that every
 * public statistic is backed by the traceability matrix. Register-appropriate
 * plain language (no security jargon), no legal-verdict vocabulary, honest
 * numbers only.
 */
import { Link } from "react-router-dom";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { TRUST_METRICS, DATA_COMMITMENTS, LINEAGE_FIELDS } from "./mockData";
import "../../components/furniture.css";
import "./trust.css";

export function TrustCenter() {
  // AC-3: never render a metric without a source note.
  const metrics = TRUST_METRICS.filter(m => m.sourceNote && m.sourceNote.trim().length > 0);

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      {/* Hero */}
      <div className="tc-hero">
        <div className="tc-hero-eyebrow">Trust Center</div>
        <h1>Intelligence you can check, line by line.</h1>
        <p>
          Visentix turns public privacy notices into benchmark intelligence — measured, not asserted. This page
          explains what we claim, how we handle your data, and how every figure we publish traces back to its
          source.
        </p>
      </div>

      {/* Trust metrics strip (M-27) */}
      <div className="tc-metrics">
        {metrics.map(m => (
          <div key={m.label} className="tc-metric">
            <div className="tc-metric-value">{m.value}</div>
            <div className="tc-metric-label">{m.label}</div>
            <div className="tc-metric-note">{m.sourceNote}</div>
          </div>
        ))}
      </div>

      {/* 1 · What we claim */}
      <section className="tc-section">
        <h2 className="tc-section-title">What we claim — and what we don't</h2>
        <p className="tc-section-lede">
          Visentix answers "compared to whom, with what exposure, at what confidence." It never answers "is this
          legal?" Our reports speak in exposure, maturity, likelihood, benchmark position, and confidence.
        </p>
        <div className="tc-claim">
          <div className="tc-claim-card do">
            <div className="tc-claim-head">We do</div>
            <ul>
              <li>Benchmark a notice against a real cohort of peers.</li>
              <li>Quantify disclosure maturity, exposure likelihood, and transparency.</li>
              <li>Show the confidence behind every figure.</li>
              <li>Point to the specific clause behind every finding.</li>
            </ul>
          </div>
          <div className="tc-claim-card dont">
            <div className="tc-claim-head">We do not</div>
            <ul>
              <li>Tell you whether a notice is legal or meets a law.</li>
              <li>Issue a determination about your practices.</li>
              <li>Offer legal advice or draft your notice for you.</li>
              <li>Publish a number we cannot trace to its source.</li>
            </ul>
          </div>
        </div>
        <div style={{ marginTop: 16 }}><IntelligenceMark /></div>
      </section>

      {/* 2 · Your data */}
      <section className="tc-section">
        <h2 className="tc-section-title">Your data</h2>
        <p className="tc-section-lede">
          Trust starts with restraint. Here is exactly what we do — and do not — do with what you send us.
        </p>
        <div className="tc-commitments">
          {DATA_COMMITMENTS.map(c => (
            <div key={c.title} className="tc-commit">
              <div className="tc-commit-title">{c.title}</div>
              <div className="tc-commit-body">{c.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 3 · How the intelligence is made */}
      <section className="tc-section">
        <h2 className="tc-section-title">How the intelligence is made</h2>
        <p className="tc-section-lede">
          Deterministic formulas, a human expert review gate, and frozen snapshots — the details are public.
        </p>
        <div className="tc-links">
          <Link to="/methodology" className="tc-link-card">
            <div className="tc-link-title">Methodology →</div>
            <div className="tc-link-desc">The 14 versioned formulas, the review gate, and reproducibility.</div>
          </Link>
          <Link to="/codex" className="tc-link-card">
            <div className="tc-link-title">Finding Codex →</div>
            <div className="tc-link-desc">Every finding code with its canonical definition and exposure signal.</div>
          </Link>
          <Link to="/crosswalk" className="tc-link-card">
            <div className="tc-link-title">Framework Crosswalk →</div>
            <div className="tc-link-desc">How our domains relate to NIST, ISO 27701, GDPR, and CCPA — descriptively.</div>
          </Link>
        </div>
      </section>

      {/* 4 · Traceability guarantee */}
      <section className="tc-section">
        <h2 className="tc-section-title">The traceability guarantee</h2>
        <p className="tc-section-lede">
          No score exists without its lineage. Every derived value stores four things, and every report
          regenerates identically from the snapshot it was frozen into.
        </p>
        <div className="tc-lineage">
          {LINEAGE_FIELDS.map(f => (
            <div key={f.field} className="tc-lineage-row">
              <span className="tc-lineage-field">{f.field}</span>
              <span className="tc-lineage-desc">{f.desc}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
