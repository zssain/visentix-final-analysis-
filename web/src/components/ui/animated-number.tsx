import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A number that counts up to its value on first appearance.
 *
 * Four rules, all load-bearing:
 *
 * 1. ARRIVAL ONLY. This animates a value appearing on screen — never a
 *    transition between two real values. A score easing 62 -> 71 would read
 *    as an improvement that never happened.
 * 2. THE FINAL VALUE IS ALWAYS THE ACCESSIBLE VALUE. `aria-label` carries the
 *    real figure from the first frame; the animating text is aria-hidden. A
 *    number that is only correct once it finishes is unreadable to a screen
 *    reader and untestable.
 * 3. REDUCED MOTION LANDS INSTANTLY. Also the default when `matchMedia` is
 *    absent (jsdom), which keeps tests deterministic rather than racing rAF.
 * 4. NEVER IN THE PDF. The print renderer is WeasyPrint/Playwright and OD-18
 *    already has byte-identity failing; nothing here may reach it.
 */
export function AnimatedNumber({
  value, decimals = 0, suffix, className, durationMs = 700,
}: {
  value: number; decimals?: number; suffix?: React.ReactNode;
  className?: string; durationMs?: number;
}) {
  const prefersReduced =
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function" ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const [shown, setShown] = React.useState(prefersReduced ? value : 0);

  React.useEffect(() => {
    if (prefersReduced) { setShown(value); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // easeOutCubic — decelerates into the value rather than snapping
      setShown(value * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setShown(value);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs, prefersReduced]);

  const final = value.toFixed(decimals);
  return (
    <span className={cn("tabular-nums", className)} aria-label={final}>
      <span aria-hidden="true">{shown.toFixed(decimals)}</span>
      {suffix}
    </span>
  );
}
