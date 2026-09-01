/**
 * F13 — Framework Crosswalk Explorer · UI (built against mocks, M-25).
 *
 * Shows how the 8 disclosure domains + their finding codes RELATE TO the
 * NIST Privacy Framework, ISO 27701, GDPR, and CCPA/CPRA. Descriptive-only —
 * references, never compliance verdicts (business-logic §2, F13 guardrail).
 * Public route; data mocked ahead of the framework_reference backend + OD-01
 * copy sign-off.
 */
import { Fragment, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { MockBadge } from "@/components/MockBadge";
import { CodexTooltip } from "../../components/CodexTooltip";
import {
  FRAMEWORKS, DOMAINS, MAPPINGS, cellMappings, type FrameworkId,
} from "./mockData";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Info } from "lucide-react";

/* One header/cell rule for the matrix, so a column added later cannot arrive
   with different padding from the rest. */
const TH = "sticky top-0 border-b bg-muted/40 px-3.5 py-3 text-left align-top text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground";
const TD = "border-b px-3.5 py-3 text-left align-top";

export function FrameworkCrosswalk() {
  const [activeFw, setActiveFw] = useState<FrameworkId | "all">("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const visibleFrameworks = activeFw === "all"
    ? FRAMEWORKS
    : FRAMEWORKS.filter(f => f.id === activeFw);

  const toggleDomain = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader
        eyebrow="Crosswalk"
        title="Framework Crosswalk"
        description="How Visentix's disclosure domains and finding codes relate to the frameworks you already report against. Descriptive references — not compliance determinations."
        actions={<MockBadge id="M-25" />}
      />

      {/* Descriptive-only guardrail banner (AC-5) */}
      <Alert className="mb-5">
        <Info />
        <AlertDescription>
          <b>These are descriptive references, not compliance determinations.</b> A mapping means a domain or
          finding code <i>relates to</i> a framework provision — it does not state that any organisation meets,
          satisfies, or fails it. Citations are references, not legal advice.
        </AlertDescription>
      </Alert>

      {/* Framework filter (AC-2) */}
      <div className="mb-5 flex flex-wrap gap-2">
        {([{ id: "all" as const, name: "All frameworks" }, ...FRAMEWORKS]).map(f => (
          <Button
            key={f.id}
            type="button"
            size="sm"
            variant={activeFw === f.id ? "default" : "outline"}
            aria-pressed={activeFw === f.id}
            onClick={() => setActiveFw(f.id as FrameworkId | "all")}
            className="rounded-full"
          >
            {f.name}
          </Button>
        ))}
      </div>

      {/* Matrix (AC-1, AC-6) */}
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr>
              <th className={cn(TH, "min-w-[170px]")}>Domain</th>
              {visibleFrameworks.map(f => <th key={f.id} className={TH}>{f.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {DOMAINS.map(d => {
              const isOpen = expanded.has(d.id);
              return (
                <Fragment key={d.id}>
                  <tr>
                    <td className={cn(TD, "whitespace-nowrap")}>
                      <span className="flex items-center gap-2 text-[0.9rem] font-bold">
                        <Badge className="font-data">{d.id}</Badge>{d.name}
                      </span>
                      <Button
                        variant="link" size="sm"
                        className="mt-1 h-auto p-0 text-[0.74rem]"
                        aria-expanded={isOpen}
                        onClick={() => toggleDomain(d.id)}
                      >
                        {isOpen ? "Hide finding codes" : `Show ${d.codes.length} finding codes`}
                      </Button>
                    </td>
                    {visibleFrameworks.map(f => {
                      const cells = cellMappings(d.id, f.id).filter(m => m.code === null);
                      return (
                        <td key={f.id} className={TD}>
                          {cells.length === 0 ? (
                            <span className="text-sm italic text-muted-foreground">— no direct reference</span>
                          ) : (
                            cells.map((m, i) => (
                              <div key={i} className="mb-2.5 last:mb-0">
                                <div className="font-data text-[0.82rem] font-bold">{m.citation}</div>
                                <div className="mt-0.5 text-[0.78rem] leading-snug text-muted-foreground">{m.note}</div>
                              </div>
                            ))
                          )}
                        </td>
                      );
                    })}
                  </tr>

                  {isOpen && (
                    <tr>
                      <td colSpan={visibleFrameworks.length + 1} className={cn(TD, "bg-muted/40")}>
                        <div className="mb-2 text-[0.72rem] font-bold uppercase tracking-wider text-muted-foreground">
                          {d.name} · finding codes and what they relate to
                        </div>
                        {d.codes.map(code => {
                          const codeMaps = MAPPINGS.filter(m => m.domainId === d.id && m.code === code
                            && (activeFw === "all" || m.framework === activeFw));
                          return (
                            <div key={code} className="mb-1.5 flex items-baseline gap-2 last:mb-0">
                              {/* DDR-006: finding codes are hover/focus Codex targets */}
                              <CodexTooltip code={code} />
                              <span className="flex-1">
                                {codeMaps.length === 0 ? (
                                  <span className="text-sm italic text-muted-foreground">no code-specific reference{activeFw === "all" ? "" : " for this framework"}</span>
                                ) : (
                                  codeMaps.map((m, i) => (
                                    <span key={i} className="mb-0.5 block">
                                      <span className="font-data text-[0.82rem] font-bold">{m.citation}</span>
                                      <span className="text-[0.78rem] text-muted-foreground"> — {m.note}</span>
                                    </span>
                                  ))
                                )}
                              </span>
                            </div>
                          );
                        })}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
