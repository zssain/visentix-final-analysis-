import { useState } from "react";
import { CodexTooltip } from "../../components/CodexTooltip";
import { domainLabel } from "../../lib/domainLabels";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ExemplarEntry {
  domain: string;
  your_text?: string;
  exemplar_text: string;
  maturity_note?: string;
  finding_code?: string;
  cohort_size?: number;
  cohort_date?: string;
}

type DiffSeg = { text: string; type: "same" | "added" | "removed" };

/** Word-level diff (LCS) from `a` (your notice) to `b` (exemplar):
 *  words only in `b` are additions (gold), only in `a` are removals
 *  (warm-gray strikethrough). Deterministic — pure display, no scoring. */
function wordDiff(a: string, b: string): DiffSeg[] {
  const aw = a.split(/(\s+)/).filter(Boolean);
  const bw = b.split(/(\s+)/).filter(Boolean);
  const n = aw.length, m = bw.length;
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i][j] = aw[i] === bw[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out: DiffSeg[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (aw[i] === bw[j]) { out.push({ text: aw[i], type: "same" }); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) { out.push({ text: aw[i], type: "removed" }); i++; }
    else { out.push({ text: bw[j], type: "added" }); j++; }
  }
  while (i < n) { out.push({ text: aw[i], type: "removed" }); i++; }
  while (j < m) { out.push({ text: bw[j], type: "added" }); j++; }
  return out;
}

function DiffView({ your, exemplar }: { your: string; exemplar: string }) {
  const segs = wordDiff(your, exemplar);
  return (
    <p className="m-0 text-sm leading-loose">
      {segs.map((s, i) => {
        /* Not colour-alone: an addition is highlighted AND marked <ins>, a
           removal is struck through AND marked <del>, so the diff survives a
           reader who cannot distinguish the two tints. */
        if (s.type === "added")
          return <ins key={i} className="rounded-xs bg-[color-mix(in_oklab,var(--provisional)_22%,transparent)] text-[var(--provisional)] no-underline">{s.text}</ins>;
        if (s.type === "removed")
          return <del key={i} className="text-muted-foreground">{s.text}</del>;
        return <span key={i}>{s.text}</span>;
      })}
    </p>
  );
}

export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const entries   = (content.entries as ExemplarEntry[]) ?? [];
  const [showDiff, setShowDiff] = useState(false);  // off by default

  if (entries.length === 0) {
    return (
      <div data-testid="section-8" className="report-section">
        <SectionHeading n={8} title="Benchmark Language Comparison" />
        <div data-testid="exemplar-placeholder"
          className="rounded-lg border border-dashed border-[var(--provisional)] bg-[color-mix(in_oklab,var(--provisional)_8%,transparent)] px-5 py-4 text-sm text-muted-foreground">
          No substantive notice clause is available for a domain comparison.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="section-8" className="report-section">
      <SectionHeading n={8} title="Benchmark Language Comparison" />
      <div className="flex justify-between items-center gap-4 mb-4 flex-wrap">
        <p className="m-0 max-w-prose text-sm text-muted-foreground">
          Your notice language by disclosed domain, with an approved peer comparator only where the evidence gates are met.
        </p>
        {/* Show-differences toggle (off by default): gold = language the exemplar
            adds, warm-gray strikethrough = language it drops. */}
        <Button
          type="button"
          variant={showDiff ? "secondary" : "outline"}
          size="sm"
          onClick={() => setShowDiff(v => !v)}
          aria-pressed={showDiff}
          data-testid="diff-toggle"
          className="shrink-0"
        >
          {showDiff ? "Hide differences" : "Show differences"}
        </Button>
      </div>
      {showDiff && (
        <div className="text-xs text-muted-foreground mb-3.5">
          {/* The legend used to read "gold = exemplar adds", naming a colour a
              reader may not perceive. It now names the MARK, not the hue. */}
          <ins className="rounded-xs bg-[color-mix(in_oklab,var(--provisional)_22%,transparent)] px-1 text-[var(--provisional)] no-underline">highlighted</ins> = the exemplar adds this ·{" "}
          <del className="text-muted-foreground">struck through</del> = your notice does not have it
        </div>
      )}

      {entries.map((e, i) => {
        const yourText     = (e.your_text ?? "").trim();
        const exemplarText = (e.exemplar_text ?? "").trim();
        const hasYour      = yourText.length > 0;
        const hasExemplar  = exemplarText.length > 0;
        const displayDomain = domainLabel(e.domain);

        return (
          <div key={i} className="mb-7">
            {/* Domain header */}
            <div className="flex items-center gap-2.5 mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{displayDomain.toUpperCase()}</span>
              {/* DDR-006: finding codes are hover/focus Codex targets */}
              {e.finding_code && <CodexTooltip code={e.finding_code} />}
            </div>

            {/* Diff view — merged single column when toggled on and both sides exist */}
            {showDiff && hasExemplar && hasYour ? (
              <div className="rounded-lg border bg-muted/40 px-4.5 py-4">
                <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Your Notice → Exemplar (differences)
                </div>
                <DiffView
                  your={yourText.length > 500 ? yourText.slice(0, 500) : yourText}
                  exemplar={exemplarText.length > 500 ? exemplarText.slice(0, 500) : exemplarText}
                />
              </div>
            ) : (
            /* Content cards */
            <div className={cn(
              "grid overflow-hidden rounded-lg border",
              hasYour ? "md:grid-cols-2" : "grid-cols-1"
            )}>
              {/* Your clause */}
              <div className={cn("px-4.5 py-4", hasExemplar && hasYour && "md:border-r")}>
                <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Your Notice
                </div>
                {hasYour ? (
                  <p className="m-0 text-sm leading-relaxed">
                    {yourText.length > 500 ? yourText.slice(0, 500) + "…" : yourText}
                  </p>
                ) : (
                  <p className="m-0 text-sm italic leading-relaxed text-muted-foreground">
                    Your privacy notice does not appear to include a dedicated clause
                    for {displayDomain}.
                  </p>
                )}
              </div>

              {/* Exemplar */}
              {hasExemplar && (
                <div className="bg-muted/40 px-4.5 py-4">
                  <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Approved Peer Comparator
                  </div>
                  <p className="m-0 text-sm leading-relaxed">
                    {exemplarText.length > 500 ? exemplarText.slice(0, 500) + "…" : exemplarText}
                  </p>
                </div>
              )}
              {!hasExemplar && (
                <div className="bg-muted/40 px-4.5 py-4">
                  <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Approved Peer Comparator
                  </div>
                  <p className="m-0 text-sm italic leading-relaxed text-muted-foreground">
                    No comparable approved peer language is available for this domain.
                  </p>
                </div>
              )}
            </div>
            )}

            {/* Footer */}
            {e.maturity_note && (
              <div className="flex items-center gap-2 rounded-b-lg border border-t-0 bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {/* Honest n only — never a fabricated fallback (M-12 / Hard Rule 7) */}
                  {e.cohort_size ? `Cohort: n=${e.cohort_size} peers` : "Cohort size unavailable"}
                </span>
                <span className="italic">· {e.maturity_note}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
