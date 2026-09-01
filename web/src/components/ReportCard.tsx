/**
 * ReportCard — the latest report, as an object you can pick up.
 *
 * Shaped like the thing it opens: 8.5:11, the ratio of the page it prints to.
 *
 * WHY IT IS NOT IN components/ui. That folder holds vendored shadcn primitives
 * and is EXEMPT from `scripts/check_colors.py` — a component with a score-driven
 * gradient is exactly what that guard exists for, so putting it there would buy
 * a visual effect by switching off the check that keeps colour meaningful.
 *
 * THE GRADIENT IS THE BAND, NOT DECORATION. The showcase this is adapted from
 * picks arbitrary hues per card (#ffbc00 -> #ff0058, and so on). In this product
 * colour is a judgement: green good, yellow middling, red poor (OD-13), and a
 * decorative hue on a card that also shows a score would either compete with
 * that reading or quietly contradict it. So the gradient is mixed from the
 * score's own standing colour. A card with no score gets a neutral wash — never
 * a pretty one, because "we could not score this" must not look better than a
 * poor result.
 *
 * MOTION. Tilt and parallax are pointer feedback, not value animation, so §7's
 * arrival rule does not apply — but they are still disabled entirely under
 * `prefers-reduced-motion`, and the card is a real link, so a keyboard user gets
 * the same destination with no motion at all.
 */
import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { maturityBand, maturityBandColor } from "../lib/scoreBands";
import { cn } from "@/lib/utils";

export interface ReportCardProps {
  /** Organisation the report was prepared for. */
  organization: string;
  /** Overall score, or undefined when this card must not claim one. */
  score?: number;
  /** Why there is no score, in the reader's words. Required when score is absent. */
  scoreAbsenceReason?: string;
  /** Assessment/notice id — the card links to its report. */
  reportId: string;
  meta?: { label: string; value: string }[];
}

/** Max tilt in degrees. Small on purpose: a card that swings reads as a toy. */
const MAX_TILT = 7;

function prefersReducedMotion(): boolean {
  return typeof window === "undefined"
    || typeof window.matchMedia !== "function"
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function ReportCard({
  organization, score, scoreAbsenceReason, reportId, meta = [],
}: ReportCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0, px: 0, py: 0 });
  const [lifted, setLifted] = useState(false);

  const onMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (prefersReducedMotion()) return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    // -0.5 … 0.5 from the card's centre, so the tilt is symmetric and the
    // parallax offset has a natural zero at the middle.
    const nx = (e.clientX - r.left) / r.width - 0.5;
    const ny = (e.clientY - r.top) / r.height - 0.5;
    setTilt({ x: -ny * MAX_TILT, y: nx * MAX_TILT, px: nx, py: ny });
  }, []);

  const onLeave = useCallback(() => {
    setTilt({ x: 0, y: 0, px: 0, py: 0 });
    setLifted(false);
  }, []);

  const hasScore = typeof score === "number";
  const band = hasScore ? maturityBand(score) : null;
  const standing = hasScore ? maturityBandColor(score) : "var(--muted-foreground)";

  return (
    <div className="report-card-stage" data-testid="report-card">
      <div
        ref={ref}
        className={cn("report-card", lifted && "report-card-lifted")}
        onMouseMove={onMove}
        onMouseEnter={() => !prefersReducedMotion() && setLifted(true)}
        onMouseLeave={onLeave}
        style={{
          // One custom property drives the gradient, the glow and the rules, so
          // the standing can never be right in one place and stale in another.
          ["--standing" as string]: standing,
          ["--tilt-x" as string]: `${tilt.x}deg`,
          ["--tilt-y" as string]: `${tilt.y}deg`,
          ["--par-x" as string]: `${tilt.px * 14}px`,
          ["--par-y" as string]: `${tilt.py * 14}px`,
        }}
      >
        {/* Skewed panels behind the sheet — the showcase's effect, re-coloured
            so the wash is the band. aria-hidden: it repeats what the band label
            already says in words. */}
        <span className="report-card-panel" aria-hidden="true" />
        <span className="report-card-panel report-card-panel-blur" aria-hidden="true" />

        {/* The sheet. Parallax runs opposite the panels so the two separate in
            depth rather than sliding together. */}
        <Link to={`/reports/${reportId}`} className="report-card-sheet">
          <div className="report-card-eyebrow">Latest report</div>

          <h3 className="report-card-org">{organization}</h3>

          {hasScore ? (
            <div className="report-card-score">
              {/* Band leads; the figure is secondary and never alone (AC-11). */}
              <span className="report-card-band">{band}</span>
              <span className="report-card-figure">
                {score.toFixed(1)}<span className="report-card-of">/100</span>
              </span>
            </div>
          ) : (
            /* Honest absence, in the reader's words — never a dash the reader
               has to interpret, and never a zero. */
            <p className="report-card-absent">{scoreAbsenceReason ?? "No score recorded"}</p>
          )}

          {meta.length > 0 && (
            <dl className="report-card-meta">
              {meta.map(m => (
                <div key={m.label}>
                  <dt>{m.label}</dt>
                  <dd>{m.value}</dd>
                </div>
              ))}
            </dl>
          )}

          <span className="report-card-cta">Open report</span>
        </Link>
      </div>
    </div>
  );
}
