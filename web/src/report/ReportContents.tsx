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
 * Anchors, not a script: each entry is a plain `#part-N` link, so it works in a
 * saved page, with JavaScript disabled, and under the PDF renderer.
 */
import type { ReportPart } from "./sectionGroups";
import { partAnchor } from "./ReportRail";

export function ReportContents({ parts }: { parts: ReportPart[] }) {
  if (parts.length === 0) return null;

  return (
    <nav className="report-contents" aria-label="Report contents" data-testid="report-contents">
      <h2 className="report-contents-title">What is in this report</h2>
      <ol className="report-contents-list">
        {parts.map(part => (
          <li key={part.title}>
            <a href={`#${partAnchor(part)}`} className="report-contents-item">
              <span className="report-contents-num" aria-hidden="true">
                {part.n ?? "·"}
              </span>
              <span className="report-contents-body">
                <span className="report-contents-name">{part.title}</span>
                {part.lede && <span className="report-contents-lede">{part.lede}</span>}
              </span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
