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
import { Check, ChevronDown, Copy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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
    <div
      className={cn(
        "rounded-lg border bg-card",
        condensed ? "px-3 py-2" : "px-4 py-3"
      )}
      role="status"
      aria-label={`Report status: ${status}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {/* Meaning first. The identifier is machinery and sits behind a
            disclosure — a bare UUID is not a label (DDR-004, DDR-011). */}
        <span className="text-sm font-semibold">
          {frozenDate ? `Frozen ${readableDate(frozenDate)}` : "Frozen snapshot"}
        </span>

        {snapshotId && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
            className="h-6 px-1.5 text-xs text-muted-foreground"
          >
            Reference
            <ChevronDown className={cn("transition-transform motion-reduce:transition-none", open && "rotate-180")} />
          </Button>
        )}

        <Badge
          variant={status === "approved" ? "verified" : "provisional"}
          className="ml-auto"
        >
          {status === "approved" ? "Reproducible" : "Draft — Pending Review"}
        </Badge>
      </div>

      {open && snapshotId && (
        <dl className="mt-3 flex flex-col gap-1.5 border-t pt-3 text-xs">
          <div className="flex items-center gap-2">
            <dt className="w-28 shrink-0 text-muted-foreground">Snapshot ID</dt>
            <dd className="font-data truncate">{snapshotId}</dd>
            <Button
              type="button" variant="ghost" size="sm"
              onClick={copyId}
              className="ml-auto h-6 px-1.5 text-xs"
              aria-label="Copy snapshot ID"
            >
              {copied ? <Check /> : <Copy />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          {formulaVersion && (
            <div className="flex items-center gap-2">
              <dt className="w-28 shrink-0 text-muted-foreground">Formula version</dt>
              <dd className="font-data">{formulaVersion}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
