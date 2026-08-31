/**
 * SectionHeading — one heading rule for every report section.
 *
 * The report is PRESENTED as six reader-facing parts, but the frozen snapshot
 * still carries its original twelve content blocks (Hard Rule 6: a stored
 * snapshot must regenerate identically, so grouping is a presentation concern
 * and never a payload change). A block therefore needs to render either as a
 * numbered part heading or as a sub-heading inside one — decided by context,
 * so no caller has to remember.
 */
import { createContext, useContext } from "react";

/**
 * How a block's own heading should render:
 *  - "own"    — standalone (legacy/unknown context): the block titles itself.
 *  - "sub"    — one of several blocks inside a part: render a sub-heading.
 *  - "hidden" — the only block in its part: the part heading already named it,
 *               so a second heading directly beneath would just repeat it.
 */
export type HeadingMode = "own" | "sub" | "hidden";

export const NestedSectionContext = createContext<HeadingMode>("own");

export function SectionHeading({ title }: { n?: number; title: string }) {
  const mode = useContext(NestedSectionContext);
  if (mode === "hidden") return null;
  if (mode === "sub") return <h3 className="report-subhead">{title}</h3>;
  return <h2>{title}</h2>;
}
