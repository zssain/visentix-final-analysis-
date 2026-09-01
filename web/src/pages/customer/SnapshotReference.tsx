/**
 * SnapshotReference — the dashboard's provenance, on request.
 *
 * The full ribbon used to sit across the top of the screen, so the first thing
 * a reader met on their own assessments page was a snapshot identifier and a
 * frozen date: machinery, above the work. It is not removed — a score with no
 * traceable snapshot behind it is exactly what this product refuses to ship —
 * but it belongs one gesture away rather than in the primary scan path
 * (design-system §2 "machinery on command", DDR-011).
 *
 * The trigger still states the fact that matters at a glance (the data is
 * frozen, and when), so nothing is hidden — only the identifier moves.
 */
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** "2026-07-30" → "30 Jul 2026". Unparseable input is shown verbatim, never guessed. */
function readableDate(raw: string): string {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function SnapshotReference({ snapshotId, frozenDate }: {
  snapshotId: string;
  frozenDate?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copyId() {
    try {
      await navigator.clipboard.writeText(snapshotId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions, insecure context). The ID is
      // visible in the panel and selectable, so nothing is lost.
      setCopied(false);
    }
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" data-testid="snapshot-reference-trigger">
          {frozenDate ? `Frozen ${readableDate(frozenDate)}` : "Frozen snapshot"}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80" data-testid="snapshot-reference-panel">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold">Snapshot reference</span>
            <Badge variant="verified">Reproducible</Badge>
          </div>
          <dl className="flex flex-col gap-2 text-xs">
            <div className="flex items-center gap-2">
              <dt className="w-20 shrink-0 text-muted-foreground">Snapshot ID</dt>
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
            <div className="flex items-center gap-2">
              <dt className="w-20 shrink-0 text-muted-foreground">Frozen</dt>
              <dd className="font-data">{frozenDate || "Not recorded"}</dd>
            </div>
          </dl>
          <p className="m-0 text-xs leading-relaxed text-muted-foreground">
            Every figure on this page is read from this stored snapshot. Nothing is
            recomputed when the page loads.
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
