import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const FORMULAS = [
  { id: "F-001", name: "Source Reliability Score",       purpose: "Evaluates how authoritative, fresh, and complete the source record is." },
  { id: "F-002", name: "Regulatory Exposure Score",      purpose: "Weights jurisdiction importance against regulator priority and disclosure severity per domain." },
  { id: "F-003", name: "Benchmark Deviation Score",      purpose: "Quantifies how far the organisation's score is from the top quartile of its peer cohort." },
  { id: "F-004", name: "Enforcement Correlation Score",  purpose: "Measures overlap between the organisation's disclosure clauses and historical enforcement action patterns." },
  { id: "F-005", name: "Disclosure Maturity Score",      purpose: "Scores the proportion of required disclosure elements present versus the master element checklist." },
  { id: "F-006", name: "Transparency Score",             purpose: "Combines readability, clarity, and completeness indicators into a single transparency figure." },
  { id: "F-007", name: "AI Transparency Maturity",       purpose: "Evaluates how specifically the notice addresses automated and AI-driven decision-making." },
  { id: "F-008", name: "Compound Risk Score",            purpose: "Blends regulatory, disclosure, and enforcement dimensions into one compound risk indicator." },
  { id: "F-009", name: "Confidence Weighted Score",      purpose: "Adjusts risk metrics downward when source reliability is low." },
  { id: "F-010", name: "Overall Privacy Intelligence Score", purpose: "Weighted combination of all six risk dimensions into the headline score." },
  { id: "F-011", name: "Benchmark Percentile",           purpose: "The organisation's rank relative to its weighted peer cohort." },
  { id: "F-012", name: "Trend Delta",                    purpose: "The temporal shift in overall score between the current and prior snapshot. Reports 'no prior history' on first assessment." },
  { id: "F-013", name: "Alert Escalation",               purpose: "Triggers a monitoring alert when scores fall below a threshold or significant notice changes are detected." },
  { id: "F-014", name: "Confidence Index",  purpose: "How much weight to give a figure — reflects cohort size, source quality, and classification certainty. Shown on every score as its confidence." },
];

const GUARDRAIL_TERMS = [
  "violation", "violates", "illegal", "unlawful",
  "non-compliant", "breach of law", "guilty", "liable",
];

const SME_STEPS = [
  { step: "1", label: "Report generated", detail: "Scores computed, narrative drafted in house voice." },
  { step: "2", label: "SME review queue", detail: "Each finding is presented to a subject-matter expert." },
  { step: "3", label: "Confirm / Edit / Dismiss", detail: "SME confirms accuracy, edits language, or dismisses." },
  { step: "4", label: "De-identification check", detail: "Exemplar text is scanned and redacted before use." },
  { step: "5", label: "Approval", detail: "Approved report moves from draft to client-visible." },
];

/** One section heading, so all five match. */
function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-1.5 font-display text-2xl font-semibold tracking-tight">{children}</h2>
  );
}

interface MethodVersion {
  formula_count: number | null;
  versions: string[] | null;
  effective_from: string | null;
  last_effective: string | null;
}

export function Methodology() {
  /* The published method is versioned, and a reader who did not buy the report
     must be able to check it — which is why the endpoint behind this is public.
     Absence renders as absence: no version is invented if none is recorded. */
  const [mv, setMv] = useState<MethodVersion | null>(null);
  useEffect(() => {
    api.get("/formulas/method-version")
      .then(d => setMv(d as MethodVersion))
      .catch(() => setMv(null));
  }, []);

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow="Methodology"
        title="How Visentix Works"
        description="Privacy intelligence built on deterministic formulas, human expert review, and honest benchmarking. Every figure is traceable. Every report is reproducible."
      />

      {/* Method version + change policy */}
      <section className="mb-12">
        <H2>Method Version</H2>
        <Card className="gap-2 py-4">
          <CardContent className="flex flex-col gap-3 px-4">
            <dl className="grid gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Formula set
                </dt>
                <dd className="font-data text-lg font-bold">
                  {mv?.versions?.length
                    ? mv.versions.join(" · ")
                    : <span className="text-sm font-normal text-muted-foreground">Not recorded</span>}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Formulas published
                </dt>
                <dd className="font-data text-lg font-bold">
                  {mv?.formula_count ?? <span className="text-sm font-normal text-muted-foreground">Not recorded</span>}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  In effect since
                </dt>
                <dd className="font-data text-lg font-bold">
                  {mv?.effective_from ?? <span className="text-sm font-normal text-muted-foreground">Not recorded</span>}
                </dd>
              </div>
            </dl>
            <p className="max-w-prose text-sm leading-relaxed text-muted-foreground">
              Every score records the formula version that produced it, and a report
              frozen under one version is never re-scored under another — re-scoring
              creates a new snapshot and the original is kept. Where a figure's
              version is not recorded, the report says so rather than showing a
              version it cannot evidence.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* The formulas */}
      <section className="mb-12">
        <H2>14 Versioned Formulas</H2>
        <p className="mb-5 text-sm text-muted-foreground">
          Every score is the output of one of these formulas. Formula IDs are published in every report and lineage drawer.
        </p>
        <Card className="gap-0 overflow-hidden py-0">
          <ul className="divide-y">
            {FORMULAS.map(f => (
              <li key={f.id} className="flex items-start gap-4 px-4 py-3 odd:bg-muted/40">
                <Badge className="mt-0.5 font-data shrink-0">{f.id}</Badge>
                <div>
                  <div className="text-sm font-semibold">{f.name}</div>
                  <div className="text-sm leading-relaxed text-muted-foreground">{f.purpose}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      {/* Intelligence, not verdicts */}
      <section className="mb-12">
        <H2>Intelligence, Not Legal Verdicts</H2>
        <blockquote className="my-4 border-l-[3px] border-[var(--provisional)] pl-5">
          <p className="mb-2 font-display text-lg italic leading-relaxed">
            Visentix answers "compared to whom, with what exposure, at what confidence."
            It never answers "is this legal?"
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            A phrasing guardrail runs at report-draft time and hard-blocks any attempt to output legal-verdict language.
            Reports are written in exposure, maturity, likelihood, benchmark, and confidence terms only.
          </p>
        </blockquote>
        <Card className="gap-2 py-4">
          <CardContent className="px-4">
            <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Guardrail — blocked terms
            </div>
            <div className="flex flex-wrap gap-1.5">
              {GUARDRAIL_TERMS.map(t => (
                <Badge key={t} variant="standing-bad" className="line-through opacity-80">{t}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* SME review gate */}
      <section className="mb-12">
        <H2>Human Expert Review Gate</H2>
        <p className="mb-5 max-w-prose text-sm leading-relaxed text-muted-foreground">
          Every report passes through a subject-matter expert before becoming client-visible.
          Every review decision is captured as a training label for model improvement.
        </p>
        <ol className="flex flex-col">
          {SME_STEPS.map((s, i) => (
            <li key={s.step} className="flex gap-4">
              {/* Rail: the connector is drawn by the item, not by a wrapper, so
                  the last step has no dangling tail. */}
              <div className="flex flex-col items-center">
                <div className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                  i < 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                )}>{s.step}</div>
                {i < SME_STEPS.length - 1 && <div className="w-px flex-1 bg-border" />}
              </div>
              <div className="pb-6">
                <div className="text-sm font-semibold">{s.label}</div>
                <div className="mt-0.5 text-sm text-muted-foreground">{s.detail}</div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Reproducibility */}
      <section className="mb-12">
        <H2>Reproducibility &amp; Lineage</H2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {[
            { title: "Frozen Snapshots",  body: "Reports are frozen at publication. Pulling the same snapshot ID twice produces byte-identical output. Re-scoring creates a new versioned snapshot; history is never overwritten." },
            { title: "No Score Without Lineage",    body: "Every score stores its formula version, input references, confidence, and generation timestamp. Click any score in a report to see the full lineage." },
            { title: "Honest Benchmarking",    body: "Cohort sizes are always reported exactly, live-queried with their as-of date. Low-confidence labels are attached when cohort size is small. No inflated numbers." },
            { title: "Deterministic Narrative",     body: "Advisor Note prose is frozen into the snapshot. It is never regenerated at render time, eliminating LLM non-determinism from the final deliverable." },
          ].map(card => (
            <Card key={card.title} className="gap-1.5 py-4">
              <CardContent className="px-4">
                <div className="mb-1.5 text-sm font-semibold">{card.title}</div>
                <p className="text-sm leading-relaxed text-muted-foreground">{card.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* About */}
      <section className="mb-12">
        <H2>About Visentix</H2>
        <p className="max-w-prose text-sm leading-relaxed text-muted-foreground">
          Visentix is a privacy intelligence platform built by SOLRAC. It turns public privacy notices into
          benchmark-driven intelligence for regulators, legal officers, and privacy advisors — the people who
          need to understand where an organisation stands relative to its peers, with the evidence to defend that view.
        </p>
      </section>
    </div>
  );
}
