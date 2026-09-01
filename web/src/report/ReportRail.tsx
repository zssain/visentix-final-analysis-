/**
 * ReportRail — "on this page", pinned while you read.
 *
 * The contents card at the top answers "what is in this document" once. It
 * cannot answer "where am I now", which is the question that matters six parts
 * deep in a long report — especially for a reader who was forwarded it and
 * arrived by a link rather than by reading from the start.
 *
 * It is always visible. It used to reveal itself only after the contents card
 * scrolled away, which meant the one aid for "where am I" was missing for
 * exactly as long as the reader was still deciding where to go — and its
 * appearance mid-scroll was itself a distraction.
 *
 * Determinism: the rail is chrome, not content. It is `display: none` in print,
 * so it cannot reach the PDF renderer or affect a byte-identical re-pull.
 */
import { useEffect, useRef, useState } from "react";
import type { ReportPart } from "./sectionGroups";
import { cn } from "@/lib/utils";

/** The anchor id a part owns. One definition, so the rail, the contents map and
 *  the part wrapper can never disagree about where a link points. */
export function partAnchor(part: Pick<ReportPart, "n">): string {
  return `part-${part.n ?? "appendix"}`;
}

/**
 * Which part is being read, given each part's distance from the top of the
 * viewport. The part being read is the LAST one whose heading has passed the
 * reading line — not the nearest, which flips back to the previous part
 * whenever a long section's heading is far above the fold.
 *
 * Pure, so the rule is testable without a layout engine.
 */
export function activeIndexFor(tops: number[], readingLine: number): number {
  let active = 0;
  for (let i = 0; i < tops.length; i++) {
    if (tops[i] - readingLine <= 0) active = i;
  }
  return active;
}

/** Distance from the viewport top at which a heading counts as "reached". */
const READING_LINE = 140;

export function ReportRail({ parts }: { parts: ReportPart[] }) {
  const [active, setActive] = useState(0);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (parts.length === 0) return;

    function measure() {
      frame.current = null;
      const tops = parts.map(p => {
        const el = document.getElementById(partAnchor(p));
        return el ? el.getBoundingClientRect().top : Number.POSITIVE_INFINITY;
      });
      setActive(activeIndexFor(tops, READING_LINE));
    }
    function onScroll() {
      if (frame.current !== null) return;
      frame.current = window.requestAnimationFrame(measure);
    }

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
    };
  }, [parts]);

  if (parts.length === 0) return null;

  return (
    <nav className="report-rail" aria-label="On this page" data-testid="report-rail">
      <div className="report-rail-label">On this page</div>
      <ol className="report-rail-list">
        {parts.map((part, i) => (
          <li key={part.title}>
            <a
              href={`#${partAnchor(part)}`}
              className={cn("report-rail-item", i === active && "report-rail-item-active")}
              aria-current={i === active ? "true" : undefined}
            >
              <span className="report-rail-num" aria-hidden="true">{part.n ?? "·"}</span>
              <span className="report-rail-name">{part.title}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
