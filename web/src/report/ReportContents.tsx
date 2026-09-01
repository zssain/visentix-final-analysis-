/**
 * ReportContents — the reader's map of the document.
 *
 * The report opens straight into a cover and then runs six parts deep with no
 * statement of what it contains. A reader who receives it second-hand — which
 * is the case this artifact is designed for — has no way to see the shape of it
 * before committing to reading, and no way to jump to the part they were sent
 * it for. Every assurance report in the language research opens with one of
 * these.
 *
 * It lists only parts that actually rendered, so it can never promise a section
 * the snapshot does not carry.
 *
 * SUB-SECTIONS. A part that groups several stored blocks lists them beneath it.
 * A part holding ONE block does not: that block prints no heading of its own —
 * the part heading already named it — so a sub-entry there would point the
 * reader at a heading the document does not show. Same rule as above, one level
 * down: the map may not promise what the page does not print.
 *
 * The sub-entry labels are the titles the SNAPSHOT froze, which are the same
 * strings each block renders as its heading. A contents line naming a section
 * differently from the heading it scrolls to would be its own small lie.
 *
 * Anchors, not a script: each entry is a plain `#part-N` / `#section-N` link,
 * so it works in a saved page, with JavaScript disabled, and under the PDF
 * renderer.
 */
import { hasSubheadings, type PresentPart } from "./sectionGroups";
import { blockAnchor, partAnchor } from "./ReportRail";

export function ReportContents({ parts }: { parts: PresentPart[] }) {
  if (parts.length === 0) return null;

  return (
    <nav className="report-contents" aria-label="Report contents" data-testid="report-contents">
      <h2 className="report-contents-title">What is in this report</h2>
      <ol className="report-contents-list">
        {parts.map(p => (
          <li key={p.part.title}>
            <a href={`#${partAnchor(p.part)}`} className="report-contents-item">
              <span className="report-contents-num" aria-hidden="true">
                {p.part.n ?? "·"}
              </span>
              <span className="report-contents-body">
                <span className="report-contents-name">{p.part.title}</span>
                {p.part.lede && <span className="report-contents-lede">{p.part.lede}</span>}
              </span>
            </a>

            {hasSubheadings(p) && (
              <ol className="report-contents-sublist">
                {p.blocks.map(b => (
                  <li key={b.n}>
                    <a href={`#${blockAnchor(b.n)}`} className="report-contents-subitem">
                      {b.title}
                    </a>
                  </li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
