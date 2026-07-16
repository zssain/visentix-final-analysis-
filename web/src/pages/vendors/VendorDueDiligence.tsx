/**
 * F16 — Vendor Due Diligence Mode · UI (built against mocks, M-28).
 *
 * Vendor queue → procurement summary → risk-approval decision. Visentix supplies
 * EXPOSURE intelligence with evidence; the approve/decline decision is the
 * customer's own procurement action (F16 guardrail). UI-only ahead of the
 * vendor pipeline + review persistence.
 */
import { useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { FlashNotice } from "../../components/FlashNotice";
import { CodexTooltip } from "../../components/CodexTooltip";
import { useFlash } from "../../lib/useFlash";
import { VciBadge } from "../../report/VciBadge";
import { scoreBandColor, vciBand, LOW_CONFIDENCE_COHORT_N } from "../../lib/scoreBands";
import { VENDORS, STATUS_LABEL, type Vendor, type VendorStatus } from "./mockData";
import "../../components/furniture.css";
import "./vendors.css";

const STATUS_FILTERS: (VendorStatus | "all")[] = ["all", "pending", "approved", "conditional", "declined"];

export function VendorDueDiligence() {
  const [statusFilter, setStatusFilter] = useState<VendorStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<string>(VENDORS[0].id);
  const [flash, showFlash] = useFlash();

  const selected = VENDORS.find(v => v.id === selectedId) ?? VENDORS[0];
  const visible = statusFilter === "all" ? VENDORS : VENDORS.filter(v => v.status === statusFilter);
  const lowConf = selected.cohortN < LOW_CONFIDENCE_COHORT_N;

  return (
    <div>
      <PageHeader
        eyebrow="Vendors"
        title="Vendor Due Diligence"
        description="Screen a vendor's public privacy notice, review the exposure intelligence with evidence, and record your own procurement decision."
        actions={<button className="btn btn-primary" onClick={() => showFlash("Add vendor — intake→assessment pipeline wired later (M-28).")}>+ Add vendor</button>}
      />

      <FlashNotice message={flash} />

      <div className="vd-layout">
        {/* ── Queue ─────────────────────────────────────────────────────── */}
        <div>
          <div className="vd-filters">
            {STATUS_FILTERS.map(s => (
              <button key={s} className={`vd-chip ${statusFilter === s ? "on" : ""}`} aria-pressed={statusFilter === s} onClick={() => setStatusFilter(s)}>
                {s === "all" ? "All" : STATUS_LABEL[s]}
              </button>
            ))}
          </div>

          {visible.map(v => (
            <button key={v.id} className={`vd-row ${v.id === selectedId ? "selected" : ""}`} onClick={() => setSelectedId(v.id)}>
              <span>
                <span className="vd-name">{v.name}</span>
                <span className="vd-meta">
                  {v.category} · <span className={`vd-crit ${v.criticality}`}>{v.criticality}</span>
                </span>
              </span>
              <span className="vd-score" style={{ color: scoreBandColor(v.exposureScore) }}>{v.exposureScore.toFixed(1)}</span>
              <span className={`vd-status ${v.status}`}>{STATUS_LABEL[v.status]}</span>
            </button>
          ))}
          {visible.length === 0 && (
            <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: "0.86rem" }}>No vendors with this status.</div>
          )}
        </div>

        {/* ── Detail + decision ─────────────────────────────────────────── */}
        <div className="vd-card">
          <div className="vd-detail-head">
            <div>
              <div className="vd-detail-name">{selected.name}</div>
              <div className="vd-detail-sub">
                {selected.domain} · {selected.category} · submitted {selected.submitted}
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div className="vd-score" style={{ color: scoreBandColor(selected.exposureScore) }}>{selected.exposureScore.toFixed(1)}</div>
              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>exposure</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Confidence</span>
            <VciBadge label={vciBand(selected.vci)} guidance={`Result confidence: ${selected.vci}`} />
            <span style={{ fontSize: "0.76rem", color: lowConf ? "var(--gold)" : "var(--text-muted)", fontWeight: lowConf ? 700 : 400 }}>
              benchmarked vs {selected.cohortN} peers{lowConf ? " · small cohort — caution" : ""}
            </span>
          </div>

          <div className="vd-summary">{selected.summary}</div>

          <div style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 6 }}>
            Exposure signals · with evidence
          </div>
          {selected.signals.map((s, i) => (
            <div key={i} className="vd-signal">
              {/* DDR-006: every finding code is a hover/focus Codex target */}
              <span style={{ flexShrink: 0 }}><CodexTooltip code={s.code} /></span>
              <span className="vd-signal-snippet">
                <span className="vd-signal-issue">{s.issue}</span>
                “{s.snippet}”
              </span>
              <span style={{ flexShrink: 0 }}><VciBadge label={vciBand(s.vci)} guidance={`Flag confidence: ${s.vci}`} /></span>
            </div>
          ))}

          <div style={{ marginTop: 14 }}><IntelligenceMark /></div>

          {/* key remount re-seeds the panel per vendor — no setState-in-effect needed */}
          <DecisionPanel key={selected.id} vendor={selected} onFlash={showFlash} />
        </div>
      </div>
    </div>
  );
}

/** Decision panel — the customer's procurement action (AC-3, AC-4). */
function DecisionPanel({ vendor, onFlash }: { vendor: Vendor; onFlash: (msg: string) => void }) {
  const [decision, setDecision] = useState<VendorStatus>(vendor.status);
  const [note, setNote] = useState("");
  const [conditions, setConditions] = useState(vendor.conditions ?? "");

  const record = () => {
    if (decision === "pending") onFlash("Choose a decision before recording.");
    else if (!note.trim()) onFlash("Add a note explaining the decision before recording.");
    else onFlash(`Recorded your decision for ${vendor.name} — persistence wired later (M-28).`);
  };

  return (
    <div className="vd-decision">
      <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)", marginBottom: 4 }}>Your procurement decision</div>
      <div className="vd-decision-note">
        This decision is yours to record. Visentix provides exposure intelligence about this vendor's
        disclosures — it does not approve, clear, or reject a vendor for you.
      </div>
      <div className="vd-actions">
        <button className={`vd-action ${decision === "approved" ? "sel-approved" : ""}`} aria-pressed={decision === "approved"} onClick={() => setDecision("approved")}>Approve</button>
        <button className={`vd-action ${decision === "conditional" ? "sel-conditional" : ""}`} aria-pressed={decision === "conditional"} onClick={() => setDecision("conditional")}>Approve with conditions</button>
        <button className={`vd-action ${decision === "declined" ? "sel-declined" : ""}`} aria-pressed={decision === "declined"} onClick={() => setDecision("declined")}>Decline</button>
      </div>

      {decision === "conditional" && (
        <>
          <div className="vd-field-label">Conditions</div>
          <textarea className="vd-textarea" value={conditions} onChange={e => setConditions(e.target.value)} placeholder="e.g. proceed pending the vendor publishing category-level retention periods" />
        </>
      )}

      <div className="vd-field-label">Decision note</div>
      <textarea className="vd-textarea" value={note} onChange={e => setNote(e.target.value)} placeholder="Why you reached this decision" />

      <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={record}>Record decision</button>
    </div>
  );
}
