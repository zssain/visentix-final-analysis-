/**
 * F18 — Clause Rewrite (illustrative, guardrailed) · REAL UI (replaces the F14
 * mock M-26).
 *
 * Left: clause picker for an assessment (findings-flagged domains first).
 * Right: guardrailed + fabrication-verified rewrite with a token diff (gold
 * added / warm-gray struck), a NON-DISMISSIBLE watermark, and an honest
 * fallback (side-by-side vs an approved exemplar) whenever a rewrite can't be
 * safely generated. A rewrite is never shown unless BOTH guardrail AND
 * verification passed.
 */
import { useCallback, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { domainLabel } from "../../lib/labels";
import { cn } from "@/lib/utils";

const WATERMARK = "Illustrative language based on peer patterns — not legal drafting. Review with counsel.";

interface Clause { clause_id: string; raw_text: string; domain: string; }
interface DiffOp { op: "eq" | "add" | "del"; text: string; }
interface RewriteResult {
  rewrite_id: string; status: "llm" | "fallback";
  suggested_text: string | null; diff: DiffOp[]; watermark_text: string;
  guardrail_passed: boolean; verification_passed: boolean; fallback_used: boolean;
}

/** The token diff.
 *
 *  An addition is highlighted AND marked `<ins>`; a removal is struck through
 *  AND marked `<del>`. The colour is a second cue, never the only one, so the
 *  diff survives a reader who cannot distinguish the two tints. */
function DiffText({ diff }: { diff: DiffOp[] }) {
  return (
    <p className="m-0 text-sm leading-loose">
      {diff.map((op, i) => {
        if (op.op === "add") {
          return <ins key={i} className="rounded-xs bg-[color-mix(in_oklab,var(--provisional)_28%,transparent)] text-[var(--provisional)] no-underline">{op.text} </ins>;
        }
        if (op.op === "del") {
          return <del key={i} className="text-muted-foreground">{op.text} </del>;
        }
        return <span key={i}>{op.text} </span>;
      })}
    </p>
  );
}

export function NoticeRewrite() {
  const [assessmentId, setAssessmentId] = useState("");
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [flagged, setFlagged] = useState<string[]>([]);
  const [selected, setSelected] = useState<Clause | null>(null);
  const [result, setResult] = useState<RewriteResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, showFlash] = useFlash();

  const loadClauses = useCallback(async (id: string) => {
    if (!id.trim()) return;
    try {
      const data = await api.get(`/assessments/${id.trim()}/clauses`);
      setClauses(data.clauses || []); setFlagged(data.flagged_domains || []);
      setSelected(null); setResult(null);
      if (!data.clauses?.length) showFlash("No substantive clauses found for that assessment.");
    } catch (e) { showFlash(e instanceof ApiError ? (e.status === 403 ? "Not your assessment." : "Could not load clauses.") : "Load failed."); }
  }, [showFlash]);

  const rewrite = async (c: Clause) => {
    setSelected(c); setResult(null); setBusy(true);
    try {
      const r: RewriteResult = await api.post(`/assessments/${assessmentId.trim()}/clauses/${c.clause_id}/rewrite`, {});
      setResult(r);
    } catch (e) { showFlash(e instanceof ApiError ? `Rewrite failed: ${e.message}` : "Rewrite failed."); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Rewrite" title="Illustrative Clause Rewrite"
        description="A drafting aid — clearer structure, peer-informed phrasing — that never adds a practice, recipient, or purpose your clause didn't already make. Every suggestion passes a banned-term and a fabrication check; if it can't, you get a safe side-by-side comparison instead." />
      <FlashNotice message={flash} />

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          {/* The input had a placeholder and no label, so its purpose vanished
              the moment anything was typed into it. */}
          <Label htmlFor="rw-assessment">Assessment ID</Label>
          <Input
            id="rw-assessment"
            className="w-full sm:w-[340px]"
            placeholder="Assessment ID"
            value={assessmentId}
            onChange={e => setAssessmentId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && loadClauses(assessmentId)}
          />
        </div>
        <Button onClick={() => loadClauses(assessmentId)}>Load clauses</Button>
      </div>

      {clauses.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
          {/* Clause picker */}
          <Card className="max-h-[640px] gap-0 overflow-y-auto p-4">
            <div className="mb-3 font-sans font-semibold">
              Clauses{" "}
              {flagged.length > 0 && (
                <span className="text-xs font-normal text-muted-foreground">· flagged domains first</span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {clauses.map(c => {
                const isFlagged = flagged.includes(c.domain);
                const isOn = selected?.clause_id === c.clause_id;
                return (
                  <button
                    key={c.clause_id}
                    type="button"
                    onClick={() => rewrite(c)}
                    aria-pressed={isOn}
                    className={cn(
                      "w-full rounded-md border bg-card px-3 py-2.5 text-left transition-colors",
                      "hover:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      isOn && "border-ring ring-[2px] ring-ring/25",
                      /* A flagged domain is marked by a rule AND the word
                         "flagged" — the bullet it used to carry was a dot with
                         no legend, meaningful only to whoever wrote it. */
                      isFlagged && "border-l-[3px] border-l-[var(--provisional)]",
                    )}
                  >
                    <span className="mb-1 flex items-center gap-1.5 text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground">
                      {domainLabel(c.domain)}
                      {isFlagged && (
                        <span className="font-semibold normal-case tracking-normal text-[var(--provisional)]">
                          · flagged
                        </span>
                      )}
                    </span>
                    <span className="block text-[0.82rem] leading-relaxed text-muted-foreground">
                      {c.raw_text.slice(0, 140)}{c.raw_text.length > 140 ? "…" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Rewrite / diff */}
          <Card className="gap-0 p-5">
            {!selected ? (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                Pick a clause to see an illustrative rewrite.
              </div>
            ) : (
              <>
                {/* Non-dismissible by design (F18): the watermark is the reason
                    this output is safe to show at all. */}
                <div className="mb-3.5 rounded-md border border-[color-mix(in_oklab,var(--provisional)_55%,transparent)] bg-[color-mix(in_oklab,var(--provisional)_12%,var(--card))] px-3 py-2 text-sm font-semibold text-[var(--provisional)]">
                  {WATERMARK}
                </div>
                {busy ? (
                  <div className="px-5 py-10 text-center text-sm text-muted-foreground">Generating…</div>
                ) : result ? (
                  <>
                    {result.status === "llm" ? (
                      <DiffText diff={result.diff} />
                    ) : (
                      <div>
                        <p className="mb-3 rounded-md bg-muted/50 px-3 py-2 text-[0.82rem] italic leading-relaxed text-muted-foreground">
                          A safe rewrite couldn&apos;t be generated for this clause (it failed the
                          fabrication or banned-term check, or the model was unavailable). Here is
                          your clause beside an approved peer exemplar instead.
                        </p>
                        {result.diff.length ? <DiffText diff={result.diff} /> : (
                          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
                            No approved exemplar for this domain yet.
                          </div>
                        )}
                      </div>
                    )}
                    {result.suggested_text && (
                      <div className="mt-3.5 flex gap-2">
                        <Button size="sm" onClick={() => { navigator.clipboard?.writeText(result.suggested_text || ""); showFlash("Copied."); }}>Copy</Button>
                        <Button size="sm" variant="outline" onClick={() => selected && rewrite(selected)}>Regenerate</Button>
                      </div>
                    )}
                    <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                      <ins className="rounded-xs bg-[color-mix(in_oklab,var(--provisional)_28%,transparent)] px-1 text-[var(--provisional)] no-underline">added</ins>
                      <del className="text-muted-foreground">removed</del>
                    </div>
                  </>
                ) : null}
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
