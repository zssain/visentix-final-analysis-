import "@testing-library/jest-dom/vitest";

/* ── Radix pointer polyfills ────────────────────────────────────────────────
   jsdom implements neither PointerEvent nor the pointer-capture methods, and
   every Radix overlay (dropdown, select, tooltip, sheet) opens on pointerdown.
   Without these the components silently never open and tests fail with a
   misleading "unable to find role" rather than "the menu did not open".
   Shared here so this is solved once, not per test file. */
if (typeof window !== "undefined") {
  if (!window.PointerEvent) {
    // @ts-expect-error — minimal stand-in; Radix only reads standard Event bits
    window.PointerEvent = class PointerEvent extends MouseEvent {};
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
    Element.prototype.setPointerCapture = () => {};
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }

  /* jsdom has no IntersectionObserver. Anything that reveals itself on scroll
     throws on mount without it, and the failure surfaces as an unrelated React
     commit-phase stack rather than "the observer is missing". Constructing it
     is enough — this stub never fires, so a component under test renders its
     initial state, which is what a unit test should be asserting anyway. */
  if (!("IntersectionObserver" in window)) {
    class IO {
      constructor(_cb: IntersectionObserverCallback, _opts?: IntersectionObserverInit) {}
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords(): IntersectionObserverEntry[] { return []; }
      readonly root = null;
      readonly rootMargin = "";
      readonly thresholds: ReadonlyArray<number> = [];
    }
    // @ts-expect-error — minimal stand-in for the constructor surface used here
    window.IntersectionObserver = IO;
  }
}
