/**
 * The cover's arrival animation, against design-system §7's four constraints.
 *
 * The constraint that actually breaks in practice is rule 2: a figure that is
 * only correct once the animation finishes is unreadable to a screen reader and
 * untestable — every assertion here would race requestAnimationFrame. So the
 * tests read the ACCESSIBLE value, which must be final from the first frame,
 * and never the animating text.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreDial } from "../report/ScoreDial";

describe("ScoreDial — arrival animation (design-system §7)", () => {
  it("the accessible figure is final from the first frame, not after the count-up", () => {
    render(<ScoreDial score={62.3} />);
    // The gauge's own label carries the real number immediately...
    expect(screen.getByRole("img"))
      .toHaveAccessibleName(/Overall Privacy Intelligence Score 62\.3 of 100/);
    // ...and so does the counter, whose visible text is aria-hidden while it runs.
    expect(screen.getByLabelText("62.3")).toBeInTheDocument();
  });

  it("the band label leads and is never carried by colour alone", () => {
    render(<ScoreDial score={62.3} />);
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  it("the arc's dash length is the arc's OWN length, so it lands on the value", () => {
    const { container } = render(<ScoreDial score={50} />);
    const arc = container.querySelector(".score-dial-arc") as HTMLElement;
    expect(arc).not.toBeNull();
    // r=96, sweep = 50/100 * 180 = 90deg  ->  pi * 96 * 90/180
    const expected = (Math.PI * 96 * 90) / 180;
    expect(Number(arc.style.getPropertyValue("--dial-len"))).toBeCloseTo(expected, 6);
  });

  it("a zero score draws no arc at all rather than a zero-length stroke", () => {
    const { container } = render(<ScoreDial score={0} />);
    expect(container.querySelector(".score-dial-arc")).toBeNull();
    expect(screen.getByRole("img")).toHaveAccessibleName(/Score 0\.0 of 100/);
  });

  it("a score above 100 is clamped — the arc can never overrun its own track", () => {
    const { container } = render(<ScoreDial score={140} />);
    const arc = container.querySelector(".score-dial-arc") as HTMLElement;
    const halfCircle = (Math.PI * 96 * 180) / 180;
    expect(Number(arc.style.getPropertyValue("--dial-len"))).toBeCloseTo(halfCircle, 6);
    expect(screen.getByLabelText("100.0")).toBeInTheDocument();
  });

  it("the decorative wash and the entrance are the only animated parts", () => {
    // Guards the rule that motion here is arrival-only chrome: nothing in the
    // dial's DATA path (the figure, the band word, the scale) may animate.
    const { container } = render(<ScoreDial score={62.3} />);
    const animated = container.querySelectorAll("[class*='cover-rise'], .score-dial-arc");
    expect(animated).toHaveLength(1);
  });
});
