import { maturityBandColor, maturityBand, vciBand } from "../lib/scoreBands";
import { VciBadge } from "./VciBadge";
import { AnimatedNumber } from "@/components/ui/animated-number";

/**
 * ScoreDial — the cover's score gauge (MVP plan Workstream B item 1).
 *
 * The arc draws to its value and the figure counts up to it, under §7's four
 * motion constraints: arrival only, the final value accessible from the first
 * frame, reduced motion lands instantly, never in a PDF path. The last is
 * structural rather than a promise — the PDF is rendered by a separate Python
 * template (`app/services/report/renderer.py`) that never executes this
 * component or any script, so no animation here can reach it.
 *
 * Arc color follows the shared score-band rule. The VCI badge renders only when
 * a real VCI is supplied — never an invented one.
 */
interface ScoreDialProps {
  score: number;        // 0–100
  vci?: number;         // omit when the payload has none
}

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 180) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

/** Semicircular arc path from 0°(left) to `deg`° across the top. */
function arcPath(cx: number, cy: number, r: number, deg: number) {
  const start = polar(cx, cy, r, 0);
  const end = polar(cx, cy, r, deg);
  const large = deg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
}

export function ScoreDial({ score, vci }: ScoreDialProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const sweep = (clamped / 100) * 180;
  // Overall Privacy Intelligence is a MATURITY score (higher = better):
  // color follows the maturity bands so it always agrees with the band chip.
  const color = maturityBandColor(clamped);

  return (
    <div className="score-dial" data-testid="score-dial">
      {/* The viewBox is 12px taller than the arc needs so the scale labels get
          their own band BELOW the stroke. They used to sit at y=130 while the
          round line cap spans y=113..127 at x=17..31 — so "0" was drawn on top
          of the arc's own end. Both ends are now centred under their cap
          (text-anchor=middle) on a row nothing else occupies. */}
      <svg width="240" height="146" viewBox="0 0 240 146" role="img"
        aria-label={`Overall Privacy Intelligence Score ${clamped.toFixed(1)} of 100`}>
        {/* Track */}
        <path d={arcPath(120, 120, 96, 180)} fill="none" stroke="var(--border)" strokeWidth="14" strokeLinecap="round" />
        {/* Value arc — band-colored, drawn from 0 to its value.
            The dash length is the arc's own length (pi x r x sweep/180), so the
            stroke starts fully offset and lands exactly on the value. A fixed
            dash guess would over- or under-shoot at different scores. */}
        {sweep > 0 && (
          <path
            className="score-dial-arc"
            style={{ "--dial-len": `${(Math.PI * 96 * sweep) / 180}` } as React.CSSProperties}
            d={arcPath(120, 120, 96, sweep)}
            fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
          />
        )}
        {/* Scale hints — the ends of the range the arc is drawn against. */}
        <text x="24" y="143" fontSize="10" textAnchor="middle" fill="var(--muted-foreground)" fontFamily="'Source Sans 3', sans-serif">0</text>
        <text x="216" y="143" fontSize="10" textAnchor="middle" fill="var(--muted-foreground)" fontFamily="'Source Sans 3', sans-serif">100</text>
      </svg>

      {/* The figure sits INSIDE the arc (absolutely centred — the old negative
          margin pulled a two-line uppercase label down over the 0/100 scale
          hints and collided with them). Below the arc the BAND leads, because
          "Developing" is what a reader can act on and 62.3 is not
          (design-system §2). The figure is never removed — it is the arc. */}
      {/* The svg already carries the full figure in its aria-label, so the
          counter is decorative here — but AnimatedNumber keeps its own
          aria-label anyway, and the wrapper is not hidden, because a figure
          that is only correct once it finishes is unreadable (§7 rule 2). */}
      <div className="score-dial-value">
        <AnimatedNumber value={clamped} decimals={1} className="score-dial-num" durationMs={900} />
      </div>

      <div className="score-dial-caption">
        <span className="score-dial-band-word" style={{ color }}>{maturityBand(clamped)}</span>
        <span className="score-dial-label">Overall Privacy Intelligence · higher is better</span>
      </div>

      {vci !== undefined && (
        <div className="score-dial-badges">
          <VciBadge label={vciBand(vci)} guidance={`Visentix Confidence Index ${vci} — how much weight to give this figure (cohort size, source quality, classification certainty)`} />
        </div>
      )}
    </div>
  );
}
