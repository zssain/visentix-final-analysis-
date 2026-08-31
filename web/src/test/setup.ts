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
}
