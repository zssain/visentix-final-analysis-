/**
 * The sticky, collapsing page header.
 *
 * The property worth guarding is not that it collapses — it is WHAT it is
 * allowed to drop. A header that hides its own controls on scroll is worse than
 * one that does not stick at all, and a screen reader must never be read a
 * sentence that is visually gone.
 */
import { render, screen, act } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { PageHeader } from "../components/PageHeader";

function scrollTo(y: number) {
  act(() => {
    Object.defineProperty(window, "scrollY", { value: y, writable: true, configurable: true });
    window.dispatchEvent(new Event("scroll"));
    // useScrolled batches into a frame; jsdom's rAF runs on a timer.
  });
}

async function settle() {
  await act(async () => { await new Promise(r => setTimeout(r, 40)); });
}

function renderHeader() {
  return render(
    <PageHeader
      eyebrow="Assessments"
      title="Your Assessments"
      description="One sentence about the screen."
      actions={<button>Do the thing</button>}
    />
  );
}

describe("PageHeader", () => {
  beforeEach(() => {
    Object.defineProperty(window, "scrollY", { value: 0, writable: true, configurable: true });
  });

  it("renders identity, description and actions at rest", () => {
    renderHeader();
    expect(screen.getByRole("heading", { name: "Your Assessments" })).toBeInTheDocument();
    expect(screen.getByText("Assessments")).toBeInTheDocument();
    expect(screen.getByText("One sentence about the screen.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Do the thing" })).toBeInTheDocument();
  });

  it("keeps the title, the eyebrow and the actions when collapsed", async () => {
    renderHeader();
    scrollTo(400);
    await settle();
    // Where you are, and what you can do, survive the collapse.
    expect(screen.getByRole("heading", { name: "Your Assessments" })).toBeInTheDocument();
    expect(screen.getByText("Assessments")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Do the thing" })).toBeInTheDocument();
  });

  it("hides the description with `hidden`, not opacity — a hidden sentence is not read out", async () => {
    renderHeader();
    const desc = screen.getByText("One sentence about the screen.");
    expect(desc).not.toHaveClass("hidden");
    scrollTo(400);
    await settle();
    // Asserted on the class, not on computed visibility: no Tailwind stylesheet
    // is loaded in jsdom, so `toBeVisible()` passes for everything and would
    // make this test green no matter what the component did.
    //
    // `hidden` (display:none) drops the element from the accessibility tree. An
    // opacity-0 or height-0 element stays in it, and a screen reader reads out a
    // sentence the sighted reader cannot see.
    expect(desc).toHaveClass("hidden");
    expect(desc.className).not.toMatch(/opacity-0|h-0|max-h-0/);
  });

  it("the heading level never changes — collapsing must not restructure the page", async () => {
    renderHeader();
    const before = screen.getByRole("heading", { level: 1 }).tagName;
    scrollTo(400);
    await settle();
    expect(screen.getByRole("heading", { level: 1 }).tagName).toBe(before);
  });

  it("every decorative layer is hidden from assistive tech", () => {
    const { container } = renderHeader();
    // The wash, the eyebrow mark and the hairline carry no meaning; each must
    // opt out rather than be read as an unlabelled element.
    const decorative = container.querySelectorAll('[aria-hidden="true"]');
    expect(decorative.length).toBeGreaterThanOrEqual(3);
  });
});

// ── The scroll rule ───────────────────────────────────────────

import { renderHook } from "@testing-library/react";
import { useScrolled } from "../lib/useScrolled";

describe("useScrolled — hysteresis", () => {
  async function set(y: number) {
    await act(async () => {
      Object.defineProperty(window, "scrollY", { value: y, writable: true, configurable: true });
      window.dispatchEvent(new Event("scroll"));
      await new Promise(r => setTimeout(r, 40));
    });
  }

  it("collapses past the threshold and stays collapsed until well back up", async () => {
    const { result } = renderHook(() => useScrolled(48, 12));
    expect(result.current).toBe(false);

    await set(60);
    expect(result.current).toBe(true);

    // The bug this guards: collapsing and expanding at the SAME position makes
    // the header flicker whenever a reader rests near the boundary — one pixel
    // of movement flips it. At 30 it is below the collapse threshold but above
    // the release, so it must stay collapsed.
    await set(30);
    expect(result.current).toBe(true);

    await set(4);
    expect(result.current).toBe(false);
  });

  it("does not collapse for a nudge below the threshold", async () => {
    const { result } = renderHook(() => useScrolled(48, 12));
    await set(20);
    expect(result.current).toBe(false);
  });
});
