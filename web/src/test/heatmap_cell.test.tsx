/**
 * F05 AC-13 — the heatmap cell is explorable.
 *
 * "Activating any heatmap cell (mouse AND keyboard) opens its detail panel from
 * the frozen snapshot; an unevidenced cell opens to an explicit no-evidence
 * line and a below-floor cohort opens without a peer comparison. No panel
 * content is computed at render."
 *
 * Each of those four clauses gets a test, plus the one that matters most and is
 * easiest to lose in a refactor: **the panel must not invent a figure the
 * snapshot does not carry.**
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import { RegulatorExposure } from "../report/sections/RegulatorExposure";
import { LOW_CONFIDENCE_COHORT_N } from "../lib/scoreBands";

const EVIDENCED = {
  domain: "data_sharing",
  intensity: 78.4,
  rpw: 0.9,
  efw: 0.8,
  clause_density: 0.22,
  f004_boost: 0.15,
  vci: 0.4,
  evidenced: true,
};

const UNEVIDENCED = {
  domain: "children_teens",
  intensity: 6.4,          // the rpw x efw x 0.1 floor — real, but NOT about this notice
  rpw: 0.8,
  efw: 0.8,
  clause_density: 0,
  f004_boost: 0,
  vci: 0.2,
  evidenced: false,
};

function content(over: Record<string, unknown> = {}) {
  return {
    regulatory_score: 61.2,
    tier: "High",
    snapshot_id: "snap-abc-123",
    date: "2026-09-01",
    cohort_size: 23,
    cohort_date: "2026-08-15",
    heatmap: [{
      regulator_id: "REG-CA",
      regulator_name: "California Privacy Protection Agency",
      jurisdiction: "US-CA",
      cells: [EVIDENCED, UNEVIDENCED],
    }],
    ...over,
  };
}

const cellButton = (domain: string) =>
  screen.getByTestId(`heatmap-cell-REG-CA-${domain}`);

describe("F05 AC-13 — heatmap cell detail panel", () => {
  afterEach(cleanup);

  it("every cell is a real button, so it is reachable by keyboard and by mouse", () => {
    render(<RegulatorExposure content={content()} />);
    for (const domain of ["data_sharing", "children_teens"]) {
      const el = cellButton(domain);
      // A <div onClick> would pass a click test and fail every keyboard user.
      expect(el.tagName).toBe("BUTTON");
    }
  });

  it("opens on click", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);
    await user.click(cellButton("data_sharing"));
    expect(await screen.findByTestId("heatmap-cell-panel")).toBeInTheDocument();
  });

  it("opens on keyboard activation — Enter and Space both", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);

    cellButton("data_sharing").focus();
    expect(cellButton("data_sharing")).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByTestId("heatmap-cell-panel")).toBeInTheDocument();

    cleanup();
    render(<RegulatorExposure content={content()} />);
    cellButton("data_sharing").focus();
    await user.keyboard(" ");
    expect(await screen.findByTestId("heatmap-cell-panel")).toBeInTheDocument();
  });

  it("an evidenced cell leads with its band label, not a bare number (AC-11)", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getByText("High exposure")).toBeInTheDocument();
    expect(within(panel).getByTestId("cell-intensity")).toHaveTextContent("78.4");
  });

  it("an unevidenced cell opens to an explicit no-evidence line", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);
    await user.click(cellButton("children_teens"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getByTestId("cell-no-evidence")).toHaveTextContent(
      /No clause from your notice maps to/i);
  });

  it("an unevidenced cell never presents its floor intensity as exposure", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);
    await user.click(cellButton("children_teens"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    // 6.4 is a real stored number, but it measures the REGULATOR's baseline
    // interest. Rendering it as this notice's standing would be a measurement
    // nobody made.
    expect(within(panel).queryByTestId("cell-intensity")).toBeNull();
    expect(within(panel).queryByText(/exposure$/i)).toBeNull();
  });

  it("a cohort at or above the floor opens WITH a peer comparison", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content({ cohort_size: LOW_CONFIDENCE_COHORT_N })} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getByTestId("cell-cohort")).toHaveTextContent(
      `${LOW_CONFIDENCE_COHORT_N} comparable organizations`);
  });

  it("a below-floor cohort opens WITHOUT a peer comparison", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content({ cohort_size: LOW_CONFIDENCE_COHORT_N - 1 })} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).queryByTestId("cell-cohort")).toBeNull();
    expect(within(panel).getByTestId("cell-no-cohort")).toBeInTheDocument();
  });

  it("no cohort at all opens without a peer comparison, and says none exists", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content({ cohort_size: 0 })} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getByTestId("cell-no-cohort")).toHaveTextContent(/has none/i);
  });

  it("a missing input renders as absence, never as 0.00", async () => {
    const user = userEvent.setup();
    // A snapshot frozen before rpw/efw were stored: the panel must not fill the
    // gap with a plausible-looking zero (Hard Rule 7).
    render(<RegulatorExposure content={content({
      heatmap: [{
        regulator_id: "REG-CA", regulator_name: "CPPA", jurisdiction: "US-CA",
        cells: [{ domain: "data_sharing", intensity: 78.4, clause_density: 0.22, evidenced: true }],
      }],
    })} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getAllByText("—").length).toBeGreaterThan(0);
    expect(within(panel).queryByText("0.00")).toBeNull();
  });

  it("carries the snapshot's own provenance, not a placeholder", async () => {
    const user = userEvent.setup();
    render(<RegulatorExposure content={content()} />);
    await user.click(cellButton("data_sharing"));
    const panel = await screen.findByTestId("heatmap-cell-panel");
    expect(within(panel).getByText("snap-abc-123")).toBeInTheDocument();
  });

  it("the accessible name states the evidence state — colour is never the only carrier", () => {
    render(<RegulatorExposure content={content()} />);
    expect(cellButton("children_teens"))
      .toHaveAccessibleName(/no evidence from your notice/i);
    expect(cellButton("data_sharing"))
      .toHaveAccessibleName(/High exposure, 78\.4/);
  });
});
