import { useEffect, useState } from "react";

/**
 * True once the window has scrolled past `threshold`.
 *
 * Throttled to one read per animation frame: a scroll handler that calls
 * `setState` on every event runs React reconciliation dozens of times per
 * gesture, which is how a sticky header ends up feeling heavier than the page
 * it is pinned to.
 *
 * The two thresholds are deliberate. Collapsing and expanding at the SAME
 * scroll position makes a header flicker between states whenever a reader rests
 * near the boundary — one pixel of movement flips it. Expanding lower than it
 * collapses gives the state somewhere to settle.
 */
export function useScrolled(threshold = 48, release = 12): boolean {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let frame: number | null = null;

    const measure = () => {
      frame = null;
      const y = window.scrollY;
      setScrolled(prev => (prev ? y > release : y > threshold));
    };
    const onScroll = () => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [threshold, release]);

  return scrolled;
}
