import { useState } from "react";
import { CohortLabel } from "../CohortLabel";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Register = "executive" | "practitioner" | "plain";

const REGISTER_LABELS: Record<Register, string> = {
  executive:    "Executive",
  practitioner: "Practitioner",
  plain:        "Plain English",
};

export function ExecutiveSummary({ content }: { content: ReportSection["content"] }) {
  const takeaways     = (content.takeaways as string[]) ?? [];
  const summary       = content.summary as string;
  const summaryPract  = (content.summary_practitioner as string | undefined);
  const summaryPlain  = (content.summary_plain        as string | undefined);

  /* The register control used to render three badges that did nothing — a
     control that looks interactive and is not is worse than no control
     (DDR-011). It is a real selector now, and it appears ONLY when the snapshot
     actually carries alternative registers.

     The PDF is unaffected: the print renderer is Python and always emits the
     executive register, so screen interactivity cannot desynchronise it. */
  const registers: Register[] = summaryPract || summaryPlain
    ? ["executive", "practitioner", "plain"]
    : ["executive"];

  const [register, setRegister] = useState<Register>("executive");

  const textByRegister: Record<Register, string> = {
    executive:    summary,
    practitioner: summaryPract ?? summary,
    plain:        summaryPlain ?? summary,
  };

  return (
    <div data-testid="section-2" className="report-section">
      <SectionHeading n={2} title="Executive Summary" />

      {registers.length > 1 && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Tabs value={register} onValueChange={v => setRegister(v as Register)}>
            <TabsList aria-label="Reading register">
              {registers.map(r => (
                <TabsTrigger key={r} value={r}>{REGISTER_LABELS[r]}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <span className="text-xs text-muted-foreground">
            The PDF always uses the Executive register.
          </span>
        </div>
      )}

      <p className="max-w-prose text-[0.95rem] leading-relaxed">
        {textByRegister[register]}
      </p>

      {takeaways.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Key Takeaways
          </div>
          {/* Ordered: the list is in significance order (AC-19), and a numbered
              list says so where a bulleted one does not. */}
          <ol className="flex flex-col divide-y">
            {takeaways.map((t, i) => (
              <li key={i} className="flex items-start gap-2.5 py-1.5">
                <span className="mt-0.5 shrink-0 font-data text-xs font-bold text-muted-foreground">
                  {i + 1}
                </span>
                <span className="text-sm leading-relaxed text-muted-foreground">{t}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <CohortLabel size={content.cohort_size as number} date={content.cohort_date as string} />
      </div>
    </div>
  );
}
