/**
 * F12 — Bulk Analysis workflow · UI (built against mocks, M-23–M-24).
 *
 * Company-list → batch pipeline → risk-ranked queue where every flag links to
 * clause-level evidence + VCI (AC-3). Persona modes (regulator sector scan /
 * plaintiff-firm screen / audit prospecting). This is UI-only ahead of the
 * batch pipeline; the queue + evidence render from ./mockData.
 *
 * Guardrail posture: EXPOSURE intelligence with evidence references — never
 * allegations or verdicts. Honest cohort n with low-confidence caution; VCI on
 * the company result and on every individual flag. Access-controlled surface
 * (contract-gated; here gated to admin pending F10 tenancy roles).
 */
import { useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { VciBadge } from "../../report/VciBadge";
import { scoreBandColor, vciBand, LOW_CONFIDENCE_COHORT_N } from "../../lib/scoreBands";
import {
  PERSONA_MODES, ISSUE_FILTERS, BATCH_RESULTS, SECTOR_COMMON_GAPS,
} from "./mockData";
import "../../components/furniture.css";
import "./bulk.css";

export function BulkAnalysis() {
  const [mode, setMode] = useState("firm");
  const [filters, setFilters] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<number>>(new Set([1])); // top result open
  const [flash, setFlash] = useState<string | null>(null);

  const toggleFilter = (f: string) =>
    setFilters(prev => {
      const next = new Set(prev);
      next.has(f) ? next.delete(f) : next.add(f);
      return next;
    });

  const toggleRow = (rank: number) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(rank) ? next.delete(rank) : next.add(rank);
      return next;
    });

  const mockAction = (msg: string) => {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  };

  const visible = filters.size === 0
    ? BATCH_RESULTS
    : BATCH_RESULTS.filter(c => c.topIssues.some(i => filters.has(i)));

  return (
    <div>
      <PageHeader
        eyebrow="Bulk"
        title="Bulk Analysis"
        description="Screen a list of organisations at once. Results are a risk-ranked queue of exposure signals — every flag links to clause-level evidence and its confidence. Exposure intelligence, never a verdict."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => mockAction("CSV export — wired to the batch pipeline later (M-23).")}>Export CSV</button>
            <button className="btn btn-primary" onClick={() => mockAction("Evidence package export — wired later (M-24).")}>Evidence package</button>
          </div>
        }
      />

      {flash && (
        <div style={{
          background: "rgba(0,95,163,0.08)", border: "1px solid rgba(0,95,163,0.25)",
          color: "var(--exec-blue)", borderRadius: "var(--radius)", padding: "10px 16px",
          fontSize: "0.84rem", marginBottom: 20,
        }} role="status">{flash}</div>
      )}

      <div className="bulk-grid">
        {/* ── Persona mode + upload ────────────────────────────────────── */}
        <section className="bulk-card">
          <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", fontWeight: 700, marginBottom: 10 }}>
            Screening mode
          </div>
          <div className="bulk-modes">
            {PERSONA_MODES.map(m => (
              <button
                key={m.id}
                className={`bulk-mode ${mode === m.id ? "selected" : ""}`}
                aria-pressed={mode === m.id}
                onClick={() => setMode(m.id)}
              >
                <div className="bulk-mode-label">{m.label}</div>
                <div className="bulk-mode-blurb">{m.blurb}</div>
              </button>
            ))}
          </div>

          <div className="bulk-upload" style={{ marginTop: 16 }}>
            Drop a company list (CSV) or paste domains below
            <textarea
              className="bulk-textarea"
              placeholder={"aperture-retail.com\nbrightline.media\ncirrus-health.com\n…"}
              defaultValue={BATCH_RESULTS.map(c => c.company.toLowerCase().replace(/[^a-z]+/g, "-").replace(/-+$/,"") + ".com").join("\n")}
            />
            <div style={{ marginTop: 10 }}>
              <button className="btn btn-primary" onClick={() => mockAction(`Batch scan queued for ${BATCH_RESULTS.length} organisations — pipeline wired later (M-23).`)}>
                Run scan · {BATCH_RESULTS.length} organisations
              </button>
            </div>
          </div>
        </section>

        {/* ── Regulator sector view ────────────────────────────────────── */}
        {mode === "regulator" && (
          <section className="bulk-card">
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "1.1rem", color: "var(--navy)", marginBottom: 4 }}>
              Sector common gaps
            </div>
            <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 14 }}>
              Share of the scanned cohort exhibiting each disclosure gap. Descriptive prevalence, not a judgement of any one organisation.
            </div>
            {SECTOR_COMMON_GAPS.map(g => (
              <div key={g.issue} className="bulk-gap-row">
                <span className="bulk-gap-label">{g.issue}</span>
                <span className="bulk-gap-bar"><span style={{ width: `${g.sharePct}%` }} /></span>
                <span className="bulk-gap-pct">{g.sharePct}%</span>
              </div>
            ))}
          </section>
        )}

        {/* ── Ranked queue ─────────────────────────────────────────────── */}
        <section className="bulk-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 14 }}>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "1.1rem", color: "var(--navy)" }}>
                Risk-ranked queue
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                {visible.length} of {BATCH_RESULTS.length} organisations · ranked by exposure signal
              </div>
            </div>
            <div style={{ marginTop: 4 }}><IntelligenceMark /></div>
          </div>

          {/* Issue filters */}
          <div className="bulk-filters" style={{ marginBottom: 16 }}>
            {ISSUE_FILTERS.map(f => (
              <button
                key={f}
                className={`bulk-chip ${filters.has(f) ? "on" : ""}`}
                aria-pressed={filters.has(f)}
                onClick={() => toggleFilter(f)}
              >{f}</button>
            ))}
            {filters.size > 0 && (
              <button className="bulk-chip" onClick={() => setFilters(new Set())} style={{ fontStyle: "italic" }}>Clear</button>
            )}
          </div>

          {visible.map(c => {
            const isOpen = expanded.has(c.rank);
            const lowConf = c.cohortN < LOW_CONFIDENCE_COHORT_N;
            return (
              <div key={c.rank} className="bulk-row">
                <button className="bulk-row-head" aria-expanded={isOpen} onClick={() => toggleRow(c.rank)}>
                  <span className="bulk-rank">{c.rank}</span>
                  <span>
                    <span className="bulk-company">{c.company}</span>
                    <span className="bulk-industry"> · benchmarked vs {c.cohortN} peers{lowConf ? " (small cohort — caution)" : ""}</span>
                  </span>
                  <span className="bulk-industry">{c.industry}</span>
                  <span className="bulk-score" style={{ color: scoreBandColor(c.exposureScore) }}>{c.exposureScore.toFixed(1)}</span>
                  <span style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>VCI</span>
                    <VciBadge label={vciBand(c.vci)} guidance={`Result confidence: ${c.vci}`} />
                  </span>
                  <span className={`bulk-caret ${isOpen ? "open" : ""}`}>▶</span>
                </button>

                {!isOpen && (
                  <div style={{ padding: "0 14px 12px 48px" }}>
                    <div className="bulk-issues" style={{ justifyContent: "flex-start" }}>
                      {c.topIssues.map(i => <span key={i} className="bulk-issue-tag">{i}</span>)}
                    </div>
                  </div>
                )}

                {isOpen && (
                  <div className="bulk-evidence">
                    {c.evidence.map((e, idx) => (
                      <div key={idx} className="bulk-ev">
                        <div className="bulk-ev-meta">
                          <span className="clause-chip">{e.code}</span>
                        </div>
                        <div className="bulk-ev-snippet">
                          <div style={{ fontStyle: "normal", fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 4 }}>
                            {e.issue}
                          </div>
                          “{e.snippet}”
                        </div>
                        <div className="bulk-ev-meta">
                          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>VCI</span>
                          <VciBadge label={vciBand(e.vci)} guidance={`Flag confidence: ${e.vci}`} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {visible.length === 0 && (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.86rem" }}>
              No organisations match the selected issue filters.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
