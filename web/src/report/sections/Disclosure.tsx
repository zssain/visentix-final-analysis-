/**
 * Disclosure — the CLOSING bookend of the revised DDR-007.
 *
 * Replaces the per-surface "Intelligence, not legal advice" mark. Repeated on
 * every finding card and section the mark was skimmed past; stated once where
 * the reader finishes — against a scope statement where they started — it is
 * actually read.
 *
 * This is authored static copy, frozen like every other page, and it passes the
 * banned-term filter. It relaxes NOTHING: the verdict ban, VCI suppression, and
 * exposure-only vocabulary are unchanged (business-logic §2, Hard Rules 1–9).
 *
 * PRESENTATION (2026-09-01). It was four unlabelled paragraphs of identical
 * weight, each opening with a bolded phrase — so the single most important one,
 * "what it is not", had no more prominence than the other three and a reader
 * skimming found no entry point. Each is now a titled block with its question
 * as the heading, and the limits block is visually separated because it governs
 * every figure above it rather than being a fourth topic.
 */
interface DisclosureProps { cohortSize?: number; cohortDate?: string }

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="m-0 text-sm font-semibold tracking-tight text-foreground">{title}</h3>
      <p className="m-0 text-sm leading-relaxed text-muted-foreground">{children}</p>
    </div>
  );
}

export function Disclosure({ cohortSize, cohortDate }: DisclosureProps) {
  return (
    <div className="report-section report-disclosure" data-testid="report-disclosure">
      <h2>Disclosure</h2>

      {/* Three blocks, not four: the copy is approved as written and this
          change is presentation only — no sentence was added, removed or
          reworded. The last block spans both columns rather than leaving a
          hole. */}
      <div className="grid gap-6 sm:grid-cols-2 [&>*:last-child]:sm:col-span-2">
        <Block title="What this report is">
          It compares this organization's public privacy notice against the notices of
          comparable organizations and against published regulatory and enforcement signals,
          and reports where it stands, how that compares with its peer group, and how much
          confidence each figure carries. Every number traces to a stored, frozen record.
        </Block>

        <Block title="What it is not">
          It is not legal advice and does not state whether any practice meets a legal
          requirement — that judgement belongs to qualified counsel who can see the whole
          picture, including everything a public notice does not show. Visentix reads the
          published notice, not the systems, contracts, or internal controls behind it, so a
          strong notice is evidence of strong disclosure rather than proof of strong practice.
        </Block>

        <Block title="How to use it">
          Treat the comparisons as a prioritization aid: they show where this organization's
          disclosure differs from its peers and where regulators have been active, which is a
          good guide to what to look at first. Confidence labels are part of the finding — a
          figure marked lower-confidence carries a wider margin and should be weighed
          accordingly.
        </Block>

      </div>

      {/* Separated, because this governs every figure above rather than being a
          fourth topic alongside them. */}
      <div className="mt-6 rounded-lg border-l-[3px] border-l-[var(--provisional)] bg-[color-mix(in_oklab,var(--provisional)_6%,transparent)] px-4 py-3.5">
        <h3 className="m-0 mb-1.5 text-sm font-semibold tracking-tight text-foreground">
          Limits that apply to every figure here
        </h3>
        <p className="m-0 text-sm leading-relaxed text-muted-foreground">
          Comparisons are drawn from the peer cohort recorded on each section
          {typeof cohortSize === "number" && cohortSize > 0
            ? <> (n={cohortSize}{cohortDate ? <> as of {cohortDate}</> : null})</>
            : null}
          ; small cohorts are labelled and interpreted with caution. Regulatory sources reflect
          what was published as of the frozen date on this snapshot and change over time. Where
          evidence is absent, this report says so rather than estimating.
        </p>
      </div>
    </div>
  );
}
