/**
 * Report presentation structure — six reader-facing parts plus an appendix.
 *
 * WHY THIS EXISTS. The report was organized by formula: four separate numbered
 * sections each existed to present one score and a visual, so answering "how am
 * I doing" cost four page-turns; the peer-language and recommendation halves of
 * our actual positioning ("here is what comparable organizations disclose, here
 * is what we suggest") sat apart; and Traceability — machinery — held a numbered
 * slot equal in weight to the findings. This regroups the same content around
 * the questions a reader actually arrives with.
 *
 * WHAT THIS IS NOT. It is not a payload change. The frozen snapshot still
 * carries its original twelve content blocks with their original numbers, and
 * every stored snapshot — including ones frozen before this regrouping — still
 * regenerates identically (Hard Rule 6). Grouping is presentation only, and the
 * per-block `id="section-N"` anchors are preserved so lineage and deep links
 * keep resolving.
 *
 * A part renders only if at least one of its blocks is present in the payload,
 * so a legacy snapshot missing a block shows honest absence rather than an
 * empty heading.
 */
export interface ReportPart {
  /** Presented part number (1–6); the appendix is unnumbered. */
  n: number | null;
  title: string;
  /** Plain-language statement of the question this part answers. */
  lede: string;
  /** Payload section numbers composing this part, in render order. */
  blocks: number[];
  /** The cover titles itself; every other part prints a part heading. */
  headed?: boolean;
}

export const REPORT_PARTS: ReportPart[] = [
  {
    n: 1, title: "Cover & Scope", blocks: [1], headed: false,
    lede: "",
  },
  {
    n: 2, title: "Executive Summary", blocks: [2],
    lede: "",
  },
  {
    n: 3, title: "Where You Stand", blocks: [3, 4, 5, 7],
    lede: "Every score in this assessment, what each one measures, and how it compares with the peer cohort.",
  },
  {
    n: 4, title: "What We Found", blocks: [6],
    lede: "The specific disclosure gaps identified in this notice, each with the evidence behind it.",
  },
  {
    n: 5, title: "What Peers Do, What We Recommend", blocks: [8, 9, 10],
    lede: "How comparable organizations word the areas where this notice differs, and what we suggest — in priority order.",
  },
  {
    n: 6, title: "What's Changing", blocks: [12],
    lede: "Movement since the last assessment, and the regulatory developments worth watching.",
  },
  {
    n: null, title: "Appendix · Traceability & Method", blocks: [11],
    lede: "The machinery behind every figure above: snapshot, formula versions, cohort construction, and sources.",
  },
];
