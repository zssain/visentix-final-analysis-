/**
 * ProvenanceRibbon — DDR-004 (revised 2026-08-31).
 *
 * Leads with MEANING, not with the identifier: what a reader gets at a glance is
 * when the report was frozen and whether it is reproducible. The snapshot ID and
 * formula version are machinery — real, exact, and one gesture away (a reference
 * disclosure with copy-to-clipboard here, the labelled full values in
 * Traceability) — but they no longer occupy the ribbon's first position.
 * A bare UUID is not a label (design-system §2 "machinery on command", DDR-011).
 *
 * Nothing is dropped from the snapshot and reproducibility is unchanged; only the
 * default disclosure state moved from open to closed.
 */
import { useState } from "react";
import "./furniture.css";

interface ProvenanceRibbonProps {
  snapshotId: string;
  formulaVersion?: string;
  frozenDate?: string;
  status: "draft" | "approved";
  condensed?: boolean;
}

/** "2026-07-30" → "30 Jul 2026". Unparseable input is shown verbatim, never guessed. */
function readableDate(raw: string): string {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function ProvenanceRibbon({
  snapshotId,
  formulaVersion,
  frozenDate,
  status,
  condensed = false,
}: ProvenanceRibbonProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const cls = ["prov-ribbon", status, condensed ? "condensed" : ""].filter(Boolean).join(" ");

  async function copyId() {
    try {
      await navigator.clipboard.writeText(snapshotId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions, insecure context) — the ID stays
      // visible in the open panel and in Traceability, so nothing is lost.
      setCopied(false);
    }
  }

  return (
    <div className={cls} role="status" aria-label={`Report status: ${status}`}>
      <div className="ribbon-row">
        <span className="ribbon-lede">
          {frozenDate ? `Frozen ${readableDate(frozenDate)}` : "Frozen snapshot"}
        </span>

        {snapshotId && (
          <button
            type="button"
            className="ribbon-ref-toggle"
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
          >
            Reference {open ? "▴" : "▾"}
          </button>
        )}

        <div className="ribbon-mark">
          <div className="ribbon-dot" />
          {status === "approved" ? "Reproducible" : "Draft — Pending Review"}
        </div>
      </div>

      {open && snapshotId && (
        <div className="ribbon-ref">
          <div className="ribbon-ref-item">
            <span className="ribbon-ref-key">Snapshot ID</span>
            <span className="ribbon-id">{snapshotId}</span>
            <button type="button" className="ribbon-copy" onClick={copyId}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          {formulaVersion && (
            <div className="ribbon-ref-item">
              <span className="ribbon-ref-key">Formula version</span>
              <span className="ribbon-id">{formulaVersion}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
