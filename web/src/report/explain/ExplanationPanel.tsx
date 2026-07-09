/**
 * ExplanationPanel — right slide-over showing how a value was computed.
 *
 * Two registers: Plain (default, for non-experts) and Technical.
 * Always-visible cards: AI involvement, legal basis, provenance, confidence,
 * benchmark cohort, human review status, versioning footer.
 */
import { useExplain } from "./ExplainContext";
import type { ExplainEnvelope } from "./ExplainContext";
import "./explain.css";

interface Props {
  envelope: ExplainEnvelope | null;
  elementType: string;
  elementKey: string;
  label?: string;
  onClose: () => void;
}

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <div className="explain-card" data-testid={testId}>
      <div className="explain-card-title">{title}</div>
      {children}
    </div>
  );
}

export function ExplanationPanel({ envelope, elementType, elementKey, label, onClose }: Props) {
  const { register, setRegister } = useExplain();

  return (
    <div
      className="explain-overlay"
      data-testid="explain-panel"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label={`Explanation: ${label ?? elementKey}`}
    >
      <div className="explain-drawer" role="document">
        {/* Header */}
        <div className="explain-header">
          <div>
            <div className="explain-title">{envelope?.title ?? label ?? elementKey}</div>
            <div className="explain-subtitle">{elementType} · {elementKey}</div>
          </div>
          <button className="explain-close" onClick={onClose} aria-label="Close" data-testid="explain-close">&times;</button>
        </div>

        {/* Register toggle */}
        <div className="explain-register-toggle" role="tablist" aria-label="Explanation detail level">
          <button role="tab" aria-selected={register === "plain"} className={register === "plain" ? "active" : ""} onClick={() => setRegister("plain")}>Plain</button>
          <button role="tab" aria-selected={register === "technical"} className={register === "technical" ? "active" : ""} onClick={() => setRegister("technical")}>Technical</button>
        </div>

        {/* Content */}
        <div className="explain-body">
          {!envelope ? (
            <div className="explain-loading" data-testid="explain-loading">
              <div className="explain-skeleton" /><div className="explain-skeleton" /><div className="explain-skeleton short" />
              <p style={{ textAlign: "center", color: "var(--text-muted)", marginTop: 12, fontSize: "0.82rem" }}>
                Loading explanation…
              </p>
            </div>
          ) : (
            <>
              {/* Main content by register */}
              {register === "plain" ? (
                <PlainView envelope={envelope} elementType={elementType} />
              ) : (
                <TechnicalView envelope={envelope} />
              )}

              {/* Always-visible cards */}
              <Card title="Was AI involved?" testId="card-ai">
                <p className="explain-text">
                  {(envelope.llm_involvement as Record<string, unknown>)?.used
                    ? `Yes — ${(envelope.llm_involvement as Record<string, unknown>).role}`
                    : `No — ${(envelope.llm_involvement as Record<string, unknown>).role || "This value is computed by a fixed deterministic formula. No AI model is involved."}`
                  }
                </p>
                {(envelope.llm_involvement as Record<string, unknown>)?.model ? (
                  <div className="explain-meta">Model: {String((envelope.llm_involvement as Record<string, unknown>).model)}</div>
                ) : null}
              </Card>

              {Array.isArray(envelope.legal_basis) && envelope.legal_basis.length > 0 && (
                <Card title="Legal basis" testId="card-legal">
                  {envelope.legal_basis.map((lr, i) => {
                    const framework = String(lr.framework ?? "");
                    const citation = String(lr.citation ?? "");
                    const summary = String(lr.summary ?? lr.title ?? "");
                    const url = String(lr.official_url ?? "");
                    const rationale = String(lr.rationale ?? "");
                    return (
                      <div key={i} className="legal-ref">
                        <div className="legal-ref-header">
                          <span className="legal-framework">{framework}</span>
                          <span className="legal-citation">{citation}</span>
                          {lr.is_primary ? <span className="badge-primary">Primary</span> : null}
                        </div>
                        <p className="legal-summary">{summary}</p>
                        {url ? (
                          <a href={url} target="_blank" rel="noopener noreferrer" className="legal-link">
                            Official source ↗
                          </a>
                        ) : null}
                        {rationale.includes("pending") ? (
                          <span className="chip-pending">Citation pending SME review</span>
                        ) : null}
                      </div>
                    );
                  })}
                </Card>
              )}

              {envelope.database_provenance && envelope.database_provenance.length > 0 && (
                <Card title="Where this came from" testId="card-provenance">
                  {envelope.database_provenance.map((p, i) => (
                    <div key={i} className="explain-meta">
                      <strong>{String(p.table)}</strong> · Row {String(p.row_id).slice(0, 12)}
                      {Array.isArray(p.fields_used) && <> · Fields: {(p.fields_used as string[]).join(", ")}</>}
                    </div>
                  ))}
                </Card>
              )}

              <Card title="How confident is this?" testId="card-confidence">
                <p className="explain-text">{envelope.confidence_note || "Confidence data not available."}</p>
              </Card>

              <PeerComparisonCard peer_comparison={envelope.peer_comparison} />

              <Card title="Human review" testId="card-review">
                {envelope.human_review_status ? (
                  <span className="chip-reviewed">Reviewed by expert</span>
                ) : (
                  <span className="chip-pending">Automated — pending expert review</span>
                )}
              </Card>

              {/* Versioning footer */}
              <div className="explain-footer" data-testid="explain-versioning">
                {Object.entries(envelope.versioning || {}).filter(([, v]) => !!v).map(([k, v]) => (
                  <span key={k}>{k.replace(/_/g, " ")}: {String(v).slice(0, 20)}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Sub-views ─────────────────────────────────────────────── */

function PeerComparisonCard({ peer_comparison }: { peer_comparison: Record<string, unknown> }) {
  const pc = peer_comparison;
  if (!pc || pc.cohort_size == null) return null;
  const pcSize = String(pc.cohort_size);
  const pcVersion = pc.benchmark_population_version ? String(pc.benchmark_population_version) : "";
  const pcDate = pc.cohort_date ? String(pc.cohort_date) : "";
  const pcRelaxations = Array.isArray(pc.relaxations) ? (pc.relaxations as string[]) : [];
  const pcHow = pc.how_percentile_computed ? String(pc.how_percentile_computed) : "";
  return (
    <Card title="Benchmark cohort" testId="card-cohort">
      <p className="explain-text">
        Cohort size: <strong>{pcSize}</strong> normalized peers
        {pcVersion && <> · Population version: {pcVersion}</>}
        {pcDate && <> · Date: {pcDate}</>}
      </p>
      {pcRelaxations.length > 0 && (
        <div className="chip-pending" style={{ marginTop: 6 }}>
          Cohort broadened: {pcRelaxations.join(", ")}
        </div>
      )}
      {pcHow && (
        <div className="explain-meta" style={{ marginTop: 6 }}>{pcHow}</div>
      )}
    </Card>
  );
}

function PlainView({ envelope, elementType }: { envelope: ExplainEnvelope; elementType: string }) {
  if (elementType === "finding") {
    return (
      <div className="explain-audit-cards">
        <div className="audit-card">
          <div className="audit-label">Standard</div>
          <p>{envelope.legal_basis?.[0] ? `${(envelope.legal_basis[0] as Record<string, unknown>).framework}: ${(envelope.legal_basis[0] as Record<string, unknown>).citation}` : "See Legal Basis below."}</p>
        </div>
        <div className="audit-card">
          <div className="audit-label">What we observed</div>
          <p>{envelope.plain}</p>
        </div>
        <div className="audit-card">
          <div className="audit-label">Our conclusion</div>
          <p>The disclosure in this domain presents an exposure gap relative to the assessed peer cohort. This represents a maturity gap that warrants attention.</p>
        </div>
        <div className="audit-card">
          <div className="audit-label">What to do</div>
          <p>Review and strengthen disclosures in this domain to reduce exposure indicators and improve maturity positioning.</p>
        </div>
      </div>
    );
  }

  return <p className="explain-text">{envelope.plain}</p>;
}

function TechnicalView({ envelope }: { envelope: ExplainEnvelope }) {
  const tech = envelope.technical as Record<string, unknown>;
  if (!tech || Object.keys(tech).length === 0) {
    return <p className="explain-text explain-muted">Technical detail not available.</p>;
  }

  const whatRan = tech.what_ran ? String(tech.what_ran) : "";
  const formula = tech.formula ? String(tech.formula) : "";
  const output = tech.output != null ? String(tech.output) : "";
  const computation = tech.computation ? String(tech.computation) : "";

  return (
    <div className="technical-view">
      {whatRan && <div className="explain-meta"><strong>Function:</strong> {whatRan}</div>}
      {formula && <div className="explain-formula-box">{formula}</div>}
      {typeof tech.inputs === "object" && tech.inputs !== null ? (
        <table className="explain-inputs-table">
          <thead><tr><th>Input</th><th>Value</th></tr></thead>
          <tbody>
            {Object.entries(tech.inputs as Record<string, unknown>)
              .filter(([, v]) => typeof v !== "object" || v === null)
              .map(([k, v]) => (
                <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{String(v)}</td></tr>
              ))}
          </tbody>
        </table>
      ) : null}
      {output && <div className="explain-meta"><strong>Output:</strong> {output}</div>}
      {computation && <div className="explain-meta"><strong>Computation:</strong> {computation}</div>}
    </div>
  );
}
