/**
 * F16 — Vendor Due Diligence Mode · UI (built against mocks, M-28).
 *
 * Vendor queue → procurement summary → risk-approval decision. Visentix supplies
 * EXPOSURE intelligence with evidence; the approve/decline decision is the
 * customer's own procurement action (F16 guardrail). UI-only ahead of the
 * vendor pipeline + review persistence.
 */
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { humanize } from "../../lib/labels";
import { PageHeader } from "../../components/PageHeader";
import { MockBadge } from "@/components/MockBadge";
import { FlashNotice } from "../../components/FlashNotice";
import { CodexTooltip } from "../../components/CodexTooltip";
import { useFlash } from "../../lib/useFlash";
import { VciBadge } from "../../report/VciBadge";
import { scoreBandColor, vciBand, LOW_CONFIDENCE_COHORT_N } from "../../lib/scoreBands";
import { VENDORS, STATUS_LABEL, type Vendor, type VendorStatus } from "./mockData";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const STATUS_FILTERS: (VendorStatus | "all")[] = ["all", "pending", "approved", "conditional", "declined"];

/* Criticality and status are KINDS and STANDINGS, mapped once. They used to be
   a class name interpolated straight off the raw enum ("vd-crit critical"), so
   an unmapped value silently rendered an unstyled chip — and the reader saw the
   database's word, not ours. */
const CRITICALITY_VARIANT: Record<string, "standing-bad" | "standing-mid" | "secondary"> = {
  critical: "standing-bad",
  high: "standing-mid",
  standard: "secondary",
};

const STATUS_VARIANT: Record<string, "verified" | "provisional" | "standing-bad" | "secondary"> = {
  approved: "verified",
  conditional: "provisional",
  declined: "standing-bad",
  pending: "secondary",
};

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
        actions={<>
          <MockBadge id="M-28" />
          <Button onClick={() => showFlash("Adding a vendor is not wired up yet — this screen shows illustrative data.")}>+ Add vendor</Button>
        </>}
      />

      <FlashNotice message={flash} />

      <div className="grid items-start gap-5.5 lg:grid-cols-[1.15fr_1fr]">
        {/* ── Queue ─────────────────────────────────────────────────────── */}
        <div>
          <div className="mb-3.5 flex flex-wrap gap-2">
            {STATUS_FILTERS.map(s => (
              <Button key={s} type="button" size="sm" variant={statusFilter === s ? "default" : "outline"}
                className="rounded-full" aria-pressed={statusFilter === s} onClick={() => setStatusFilter(s)}>
                {s === "all" ? "All" : STATUS_LABEL[s]}
              </Button>
            ))}
          </div>

          {visible.map(v => (
            <button
              key={v.id}
              type="button"
              aria-pressed={v.id === selectedId}
              onClick={() => setSelectedId(v.id)}
              className={cn(
                "mb-2 grid w-full grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border bg-card px-3.5 py-3 text-left",
                "hover:border-ring hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                "max-md:grid-cols-[1fr_auto]",
                v.id === selectedId && "border-ring ring-[2px] ring-ring/25",
              )}
            >
              <span>
                <span className="text-[0.9rem] font-bold">{v.name}</span>
                <span className="mt-0.5 text-[0.76rem] text-muted-foreground">
                  {v.category} · <Badge variant={CRITICALITY_VARIANT[v.criticality] ?? "secondary"}>{humanize(v.criticality)}</Badge>
                </span>
              </span>
              <span className="text-right font-data text-[1.15rem] font-bold tabular-nums" style={{ color: scoreBandColor(v.exposureScore) }}>{v.exposureScore.toFixed(1)}</span>
              <Badge variant={STATUS_VARIANT[v.status] ?? "secondary"}>{STATUS_LABEL[v.status]}</Badge>
            </button>
          ))}
          {visible.length === 0 && (
            <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: "0.86rem" }}>No vendors with this status.</div>
          )}
        </div>

        {/* ── Detail + decision ─────────────────────────────────────────── */}
        <Card className="rounded-lg border bg-card px-5 py-4.5">
          <div className="mb-1 flex items-start justify-between gap-3">
            <div>
              <div className="font-sans text-[1.3rem] font-semibold">{selected.name}</div>
              <div className="mb-3.5 text-[0.8rem] text-muted-foreground">
                {selected.domain} · {selected.category} · submitted {selected.submitted}
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div className="text-right font-data text-[1.15rem] font-bold tabular-nums" style={{ color: scoreBandColor(selected.exposureScore) }}>{selected.exposureScore.toFixed(1)}</div>
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

          <div className="mb-4 text-[0.88rem] leading-relaxed text-muted-foreground">{selected.summary}</div>

          <div style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 6 }}>
            Exposure signals · with evidence
          </div>
          {selected.signals.map((s, i) => (
            <div key={i} className="flex gap-2.5 border-b py-2.5 last:border-b-0">
              {/* DDR-006: every finding code is a hover/focus Codex target */}
              <span style={{ flexShrink: 0 }}><CodexTooltip code={s.code} /></span>
              <span className="flex-1 border-l-2 border-l-muted-foreground pl-2.5 text-[0.82rem] italic leading-snug text-muted-foreground">
                <span className="mb-0.5 text-[0.68rem] font-bold uppercase not-italic tracking-wider text-muted-foreground">{s.issue}</span>
                “{s.snippet}”
              </span>
              <span style={{ flexShrink: 0 }}><VciBadge label={vciBand(s.vci)} guidance={`Flag confidence: ${s.vci}`} /></span>
            </div>
          ))}


          {/* key remount re-seeds the panel per vendor — no setState-in-effect needed */}
          <DecisionPanel key={selected.id} vendor={selected} onFlash={showFlash} />
        </Card>
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
    <div className="mt-4.5 border-t pt-4">
      <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)", marginBottom: 4 }}>Your procurement decision</div>
      <div className="mb-3 text-[0.72rem] italic leading-snug text-muted-foreground">
        This decision is yours to record. Visentix provides exposure intelligence about this vendor's
        disclosures — it does not approve, clear, or reject a vendor for you.
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Button type="button" variant={decision === "approved" ? "default" : "outline"} size="sm"
          className="min-w-[120px] flex-1"
          aria-pressed={decision === "approved"} onClick={() => setDecision("approved")}>Approve</Button>
        <Button type="button" variant={decision === "conditional" ? "default" : "outline"} size="sm"
          className="min-w-[120px] flex-1"
          aria-pressed={decision === "conditional"} onClick={() => setDecision("conditional")}>Approve with conditions</Button>
        <Button type="button" variant={decision === "declined" ? "default" : "outline"} size="sm"
          className="min-w-[120px] flex-1"
          aria-pressed={decision === "declined"} onClick={() => setDecision("declined")}>Decline</Button>
      </div>

      {decision === "conditional" && (
        <>
          <div className="mt-2.5 mb-0.5 text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">Conditions</div>
          <textarea className="mt-1 min-h-[62px] w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.82rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={conditions} onChange={e => setConditions(e.target.value)} placeholder="e.g. proceed pending the vendor publishing category-level retention periods" />
        </>
      )}

      <div className="mt-2.5 mb-0.5 text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">Decision note</div>
      <textarea className="mt-1 min-h-[62px] w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.82rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={note} onChange={e => setNote(e.target.value)} placeholder="Why you reached this decision" />

      <Button style={{ marginTop: 12 }} onClick={record}>Record decision</Button>
    </div>
  );
}
