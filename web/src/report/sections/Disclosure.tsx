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
 */
export function Disclosure({ cohortSize, cohortDate }: { cohortSize?: number; cohortDate?: string }) {
  return (
    <div className="report-section report-disclosure" data-testid="report-disclosure">
      <h2>Disclosure</h2>

      <p>
        <strong>What this report is.</strong> It compares this organization's public privacy
        notice against the notices of comparable organizations and against published regulatory
        and enforcement signals, and reports where it stands, how that compares with its peer
        group, and how much confidence each figure carries. Every number traces to a stored,
        frozen record and can be reproduced from this snapshot.
      </p>

      <p>
        <strong>What it is not.</strong> It is not legal advice and does not state whether any
        practice meets a legal requirement — that judgement belongs to qualified counsel who can
        see the whole picture, including everything a public notice does not show. Visentix reads
        the published notice, not the systems, contracts, or internal controls behind it, so a
        strong notice is evidence of strong disclosure rather than proof of strong practice.
      </p>

      <p>
        <strong>How to use it.</strong> Treat the comparisons as a prioritization aid: they show
        where this organization's disclosure differs from its peers and where regulators have
        been active, which is a good guide to what to look at first. Confidence labels are part
        of the finding — a figure marked lower-confidence carries a wider margin and should be
        weighed accordingly.
      </p>

      <p>
        <strong>Limits that apply to every figure here.</strong> Comparisons are drawn from the
        peer cohort recorded on each section
        {typeof cohortSize === "number" && cohortSize > 0
          ? <> (n={cohortSize}{cohortDate ? <> as of {cohortDate}</> : null})</>
          : null}
        ; small cohorts are labelled and interpreted with caution. Regulatory sources reflect
        what was published as of the frozen date on this snapshot and change over time. Where
        evidence is absent, this report says so rather than estimating.
      </p>
    </div>
  );
}
