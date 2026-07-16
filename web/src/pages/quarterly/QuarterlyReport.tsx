/**
 * F12 — Quarterly Global Privacy Intelligence Report · reader page.
 *
 * Public editorial page (top-of-funnel + analyst/regulator credibility asset).
 * All figures come from ./mockData (registered mocks M-15…M-18) — this is the
 * UI-first build ahead of the F12 aggregation backend. Every number here has a
 * real source named in the mock module's removal plan.
 *
 * Guardrail posture (F12): descriptive-only copy, honest cohort sizes always
 * visible, minimum-sample suppression shown, per-metric polarity delta coloring
 * (AC-8), real snapshot counts on the cover (AC-5 / Hard Rule 7).
 */
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { Link } from "react-router-dom";
import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { CodexTooltip } from "../../components/CodexTooltip";
import {
  trendColor, bandColor, maturityBandColor, LOW_CONFIDENCE_COHORT_N, type MetricPolarity,
} from "../../lib/scoreBands";
import {
  PUBLICATION, INDICATORS, KEY_FINDINGS, INDUSTRY_RANKINGS,
  REGULATOR_THEMES, REGULATOR_ACTIVITY, REGULATOR_TOP_THEMES,
  AI_GOVERNANCE_TREND, AI_DISCLOSURE_GAPS, DISCLOSURE_TRENDS,
  COMPOUND_PATTERNS, SPOTLIGHT_EXCERPTS, STRATEGIC_OUTLOOK, METHODOLOGY_FACTS,
} from "./mockData";
import "./quarterly.css";
import "../../components/furniture.css";

/* Delta chip — arrow carries DIRECTION, color carries JUDGEMENT via polarity. */
function Delta({ value, polarity }: { value: number; polarity: MetricPolarity }) {
  const color = trendColor(value, polarity);
  const glyph = value === 0 ? "■" : value > 0 ? "▲" : "▼";
  return (
    <span className="qr-delta" style={{ color }}>
      {glyph} {Math.abs(value).toFixed(1)}
    </span>
  );
}

/* Section shell keeps the editorial rhythm + numbering consistent. */
function Section({ num, title, lede, children }: {
  num?: string; title: string; lede?: string; children: React.ReactNode;
}) {
  return (
    <section className="qr-section">
      {num && <div className="qr-section-num">{num}</div>}
      <h2 className="qr-section-title">{title}</h2>
      {lede && <p className="qr-section-lede">{lede}</p>}
      {children}
    </section>
  );
}

/* Navy-intensity fill for the regulator heatmap — OBSERVED ACTIVITY, not risk,
   so it never borrows the red exposure scale (no verdict coloring). */
function activityFill(intensity: number): { bg: string; fg: string } {
  const alpha = Math.max(0.06, Math.min(1, intensity / 10));
  return {
    bg: `rgba(9,35,79,${alpha.toFixed(2)})`,
    fg: alpha > 0.55 ? "#fff" : "var(--navy)",
  };
}

export function QuarterlyReport() {
  const c = PUBLICATION.corpus;

  return (
    <div className="qr">
      {/* ── Cover ─────────────────────────────────────────────────────── */}
      <div className="qr-cover">
        {/* Snapshot surface → provenance ribbon (DDR-004). Approved = reproducible. */}
        <ProvenanceRibbon
          snapshotId={PUBLICATION.snapshotId}
          formulaVersion={PUBLICATION.formulaVersions}
          frozenDate={PUBLICATION.cutoffDate}
          status="approved"
        />
        <div className="qr-cover-hairline" aria-hidden="true" />
        <div className="qr-cover-eyebrow">Quarterly Global Privacy Intelligence · {PUBLICATION.quarter}</div>
        <h1 className="qr-cover-title">The State of Privacy Disclosure</h1>
        <p className="qr-cover-sub">Benchmark intelligence from {c.organizations} organisations, measured — not asserted.</p>

        {/* Corpus stats — REAL counts from the frozen snapshot (AC-5, Hard Rule 7). */}
        <div className="qr-cover-stats">
          <div className="qr-cover-stat">
            <div className="n">{c.organizations}</div>
            <span className="l">Organisations</span>
          </div>
          <div className="qr-cover-stat">
            <div className="n">{c.industries}</div>
            <span className="l">Industries</span>
          </div>
          <div className="qr-cover-stat">
            <div className="n">{c.jurisdictions}</div>
            <span className="l">Jurisdictions</span>
          </div>
          <div className="qr-cover-stat">
            <div className="n">{c.clausesAnalyzed.toLocaleString()}</div>
            <span className="l">Clauses analysed</span>
          </div>
        </div>

        <div className="qr-cover-foot">
          <span>Published {PUBLICATION.publishedDate} · Benchmark {PUBLICATION.benchmarkVersion}</span>
          <span className="qr-cover-mark">Assessed by Visentix</span>
        </div>
      </div>

      {/* ── 1 · Executive Summary + Intelligence Indicators ───────────────── */}
      <Section
        num="Section 1"
        title="Executive Summary"
        lede="This quarter, disclosure maturity edged upward across most industries while enforcement
              activity around deceptive design and automated decision-making continued to rise. The five
              Visentix Privacy Intelligence Indicators below are market averages, each published with its
              confidence rating and quarter-over-quarter movement."
      >
        <div className="qr-indicators">
          {INDICATORS.map(ind => (
            <div key={ind.key} className="qr-ind-card">
              <div className="qr-ind-name">{ind.name}</div>
              {/* Each indicator colors by ITS OWN polarity (design-system §2 v1.3) */}
              <div className="qr-ind-value" style={{ color: bandColor(ind.value, ind.polarity) }}>
                {ind.value.toFixed(1)}
              </div>
              <Delta value={ind.qoqDelta} polarity={ind.polarity} />
              <div className="qr-ind-blurb">{ind.blurb}</div>
              <div className="qr-ind-foot">
                <span className="qr-ind-vci">VCI {ind.vci}</span>
                <span className="qr-ind-vci" style={{ textTransform: "capitalize" }}>{ind.polarity}</span>
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16 }}><IntelligenceMark /></div>
      </Section>

      {/* ── 2 · Key Quarterly Findings ────────────────────────────────────── */}
      <Section
        num="Section 2"
        title="Key Quarterly Findings"
        lede="Six movements that defined the quarter, measured as change against the prior publication snapshot."
      >
        <div className="qr-tiles">
          {KEY_FINDINGS.map(t => (
            <div key={t.label} className="qr-tile">
              <div className="qr-tile-value">{t.value}</div>
              <div style={{ marginTop: 4 }}><Delta value={t.qoqDelta} polarity={t.polarity} /></div>
              <div className="qr-tile-label">{t.label}</div>
              <div className="qr-tile-note">{t.note}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 3 · Industry Benchmark Rankings ───────────────────────────────── */}
      <Section
        num="Section 3"
        title="Industry Benchmark Rankings"
        lede="Disclosure Maturity Index by industry, best to worst. Cohort size is shown for every row —
              industries below the low-confidence threshold are flagged, never hidden."
      >
        <div>
          {INDUSTRY_RANKINGS.map(r => {
            const low = r.cohortN < LOW_CONFIDENCE_COHORT_N;
            return (
              <div key={r.industry} className="qr-rank-row">
                <span className="qr-rank-industry">{r.industry}</span>
                <span className="qr-rank-bar">
                  {/* DMI is a maturity index — maturity color scale */}
                  <span style={{ width: `${r.dmi}%`, background: maturityBandColor(r.dmi) }} />
                </span>
                <span className="qr-rank-val">
                  {r.dmi.toFixed(1)}
                  <span style={{ marginLeft: 8 }}><Delta value={r.qoqDelta} polarity="maturity" /></span>
                </span>
                <span className={`qr-cohort ${low ? "low" : ""}`} title={low ? "Below low-confidence cohort threshold" : undefined}>
                  n={r.cohortN}{low ? " · low-confidence" : ""}
                </span>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── 4 · Regulator & Enforcement Intelligence ──────────────────────── */}
      <Section
        num="Section 4"
        title="Regulator & Enforcement Intelligence"
        lede="Observed regulatory and guidance activity by theme this quarter. Cells show counts of observed
              activity — a descriptive record, not a risk score — so shading reads as volume, not verdict."
      >
        <div className="qr-heatmap">
          <div
            className="qr-heatmap-grid"
            style={{ gridTemplateColumns: `minmax(150px, 1.3fr) repeat(${REGULATOR_THEMES.length}, 1fr) auto` }}
          >
            {/* header row */}
            <div className="qr-heat-head" />
            {REGULATOR_THEMES.map(t => <div key={t} className="qr-heat-head">{t}</div>)}
            <div className="qr-heat-head">QoQ</div>
            {/* body */}
            {REGULATOR_ACTIVITY.map(row => (
              <Row key={row.regulator} row={row} />
            ))}
          </div>
        </div>
        <ul className="qr-outlook" style={{ marginTop: 18 }}>
          {REGULATOR_TOP_THEMES.map(t => <li key={t}>{t}</li>)}
        </ul>
      </Section>

      {/* ── 5 · AI Governance Intelligence ────────────────────────────────── */}
      <Section
        num="Section 5"
        title="AI Governance Intelligence"
        lede="The AI Transparency Index (F-007) over six quarters, with the most common gaps in how notices
              describe automated and AI-driven decision-making."
      >
        <div style={{
          background: "var(--bg-card)", border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)", padding: "18px 16px 8px", marginBottom: 16,
        }}>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={AI_GOVERNANCE_TREND} margin={{ top: 6, right: 12, bottom: 0, left: -18 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E8ED" vertical={false} />
              <XAxis dataKey="quarter" tick={{ fontSize: 12, fill: "#8896A5" }} axisLine={{ stroke: "#D9DDE2" }} tickLine={false} />
              <YAxis domain={[0, 60]} tick={{ fontSize: 12, fill: "#8896A5" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: "1px solid #D9DDE2", fontSize: 12, fontFamily: "var(--font-data)" }}
                formatter={(v) => [Number(v).toFixed(1), "AI Transparency Index"]}
              />
              <Line type="monotone" dataKey="index" stroke="#55C7B3" strokeWidth={2.5} dot={{ r: 3, fill: "#55C7B3" }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="section-label" style={{ marginBottom: 10 }}>Most common AI disclosure gaps</div>
        {AI_DISCLOSURE_GAPS.map(g => (
          <div key={g.gap} className="qr-rank-row" style={{ gridTemplateColumns: "3fr 2fr auto" }}>
            <span className="qr-rank-industry" style={{ fontWeight: 500 }}>{g.gap}</span>
            <span className="qr-rank-bar"><span style={{ width: `${g.prevalence}%`, background: "var(--navy)" }} /></span>
            <span className="qr-rank-val">{g.prevalence}%</span>
          </div>
        ))}
      </Section>

      {/* ── 6 · Disclosure Trend Intelligence ─────────────────────────────── */}
      <Section
        num="Section 6"
        title="Disclosure Trend Intelligence"
        lede="Prevalence of adequate disclosure by domain, and how it moved quarter over quarter."
      >
        {DISCLOSURE_TRENDS.map(d => (
          <div key={d.domain} className="qr-rank-row" style={{ gridTemplateColumns: "1.6fr 3fr auto auto" }}>
            <span className="qr-rank-industry">{d.domain}</span>
            {/* Prevalence of adequate disclosure = maturity — use the maturity
                scale directly instead of the old 100-x inversion hack */}
            <span className="qr-rank-bar"><span style={{ width: `${d.prevalence}%`, background: maturityBandColor(d.prevalence) }} /></span>
            <span className="qr-rank-val">{d.prevalence}%</span>
            <span className="qr-rank-val" style={{ minWidth: 64 }}><Delta value={d.qoqDelta} polarity="maturity" /></span>
          </div>
        ))}
      </Section>

      {/* ── 7 · High-Risk Disclosure Patterns ─────────────────────────────── */}
      <Section
        num="Section 7"
        title="High-Risk Disclosure Patterns"
        lede="Compound patterns observed across the corpus, framed as exposure — the concurrence of signals,
              never an allegation about any organisation."
      >
        {COMPOUND_PATTERNS.map(p => (
          <div key={p.code} style={{
            display: "flex", alignItems: "center", gap: 14, padding: "12px 0",
            borderBottom: "1px solid var(--border)",
          }}>
            {/* DDR-006: finding codes are hover/focus Codex targets */}
            <span style={{ flexShrink: 0 }}><CodexTooltip code={p.code} /></span>
            <span style={{ flex: 1, fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{p.pattern}</span>
            <span className="qr-rank-val">{p.prevalence}%</span>
          </div>
        ))}
        <div style={{ marginTop: 16 }}><IntelligenceMark /></div>
      </Section>

      {/* ── 8 · Benchmark Spotlight ───────────────────────────────────────── */}
      <Section
        num="Section 8"
        title="Benchmark Spotlight"
        lede="Anonymised top-quartile disclosure language. Every excerpt has passed SME de-identification and
              approval and sits above the minimum-sample threshold — below-threshold cohorts are suppressed."
      >
        {(() => {
          const shown = SPOTLIGHT_EXCERPTS.filter(e => e.cohortN >= LOW_CONFIDENCE_COHORT_N);
          const suppressed = SPOTLIGHT_EXCERPTS.length - shown.length;
          return (
            <>
              {shown.map(e => (
                <div key={e.domain} className="qr-spotlight">
                  <div className="qr-spotlight-domain">{e.domain}</div>
                  <p className="qr-spotlight-text">“{e.excerpt}”</p>
                  <div className="qr-spotlight-cohort">Drawn from n={e.cohortN} top-quartile notices · de-identified</div>
                </div>
              ))}
              {suppressed > 0 && (
                <div className="qr-suppress">
                  <strong>{suppressed} exemplar{suppressed > 1 ? "s" : ""} suppressed.</strong> One or more domains
                  had a cohort below the minimum-sample threshold (n&nbsp;&lt;&nbsp;{LOW_CONFIDENCE_COHORT_N}) and were
                  withheld from publication rather than shown at low confidence.
                </div>
              )}
            </>
          );
        })()}
      </Section>

      {/* ── 9 · Strategic Outlook (descriptive-only, AC-7) ────────────────── */}
      <Section
        num="Section 9"
        title="Strategic Outlook"
        lede="Observed momentum only — where the corpus moved this quarter. Visentix reports direction of
              observed activity; it does not forecast regulator or company behaviour."
      >
        <ul className="qr-outlook">
          {STRATEGIC_OUTLOOK.map(s => <li key={s}>{s}</li>)}
        </ul>
      </Section>

      {/* ── 10 · Methodology (auto-generated from snapshot metadata) ──────── */}
      <Section
        num="Section 10"
        title="Methodology & Intelligence Engine"
        lede="Every statistic in this report is reproducible from the frozen publication snapshot below.
              Pulling the same snapshot twice yields identical figures."
      >
        <div className="qr-facts">
          {METHODOLOGY_FACTS.map(f => (
            <div key={f.label} className="qr-fact">
              <div className="qr-fact-label">{f.label}</div>
              <div className="qr-fact-value">{f.value}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 11 · About + CTA back cover ───────────────────────────────────── */}
      <div className="qr-cta">
        <h2>See where your organisation stands</h2>
        <p>
          This report is the market average. Visentix benchmarks a single privacy notice against its peer
          cohort — with the lineage and confidence to defend every figure.
        </p>
        <Link to="/intake" className="btn">Assess a privacy notice</Link>
      </div>
    </div>
  );
}

/* Heatmap body row — kept out of the map for readability. */
function Row({ row }: { row: (typeof REGULATOR_ACTIVITY)[number] }) {
  return (
    <>
      <div className="qr-heat-rowlabel">{row.regulator}</div>
      {row.intensity.map((v, i) => {
        const { bg, fg } = activityFill(v);
        return (
          <div
            key={i}
            className="qr-heat-cell"
            style={{ background: bg, color: fg }}
            title={`${row.regulator} · ${REGULATOR_THEMES[i]}: ${v} observed actions`}
          >
            {v}
          </div>
        );
      })}
      {/* Observed-activity change is a COUNT, not a judgement — neutral color,
          arrow only. Coloring it by polarity would contradict the section's own
          "volume, not verdict" rule (audit 2026-07-16). */}
      <div className="qr-heat-rowlabel" style={{ justifyContent: "flex-end" }}>
        <span className="qr-delta" style={{ color: "var(--text-muted)" }}>
          {row.activityDelta === 0 ? "■" : row.activityDelta > 0 ? "▲" : "▼"} {Math.abs(row.activityDelta)}
        </span>
      </div>
    </>
  );
}
