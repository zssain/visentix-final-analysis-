/**
 * WS3/WS4 report-section behaviors:
 *  - M-03 exemplar absence renders honest placeholder (not fabricated copy)
 *  - WS4 BenchmarkLanguage show-differences toggle (off by default, accessible)
 *  - M-05 AdvisorNote advisor prose is never fabricated when the snapshot omits it
 */
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BenchmarkLanguage } from "../report/sections/BenchmarkLanguage";
import { AdvisorNote } from "../components/AdvisorNote";

afterEach(cleanup);

const ENTRY_CONTENT = {
  sme_cleaned_available: true,
  entries: [
    {
      domain: "data_sharing",
      your_text: "We may share your data with trusted partners for business purposes.",
      exemplar_text: "We share your personal data with named service providers only for the purposes described here.",
      maturity_note: "Named recipients and purpose limitation.",
      cohort_size: 25,
    },
  ],
};

describe("BenchmarkLanguage — show-differences toggle (WS4)", () => {
  it("is off by default and accessible (aria-pressed=false)", () => {
    render(<BenchmarkLanguage content={ENTRY_CONTENT} />);
    const toggle = screen.getByTestId("diff-toggle");
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    expect(toggle.textContent).toMatch(/show differences/i);
  });

  it("toggles on and exposes the diff view with a legend", () => {
    render(<BenchmarkLanguage content={ENTRY_CONTENT} />);
    const toggle = screen.getByTestId("diff-toggle");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    expect(toggle.textContent).toMatch(/hide differences/i);
    // Legend words present when diff is shown
    expect(screen.getByText(/exemplar adds/i)).toBeInTheDocument();
  });
});

describe("BenchmarkLanguage — honest absence (M-03)", () => {
  it("renders the pending-exemplar placeholder when none are available", () => {
    render(<BenchmarkLanguage content={{ sme_cleaned_available: false, entries: [] }} />);
    expect(screen.getByTestId("exemplar-placeholder")).toBeInTheDocument();
  });
});

describe("AdvisorNote — advisor prose from snapshot only (M-05)", () => {
  const base = {
    findingCode: "SH-002", title: "t", domain: "data_sharing",
    status: "approved" as const, snapshotId: "snap-1",
    exposureScore: 60, cohortPercentile: 70, vci: 62,
    formulaId: "F-002", formulaDesc: "desc", cohortSize: 25, cohortDate: "2026-07-20",
  };

  it("shows honest absence when the snapshot carries no advisor prose", () => {
    render(<AdvisorNote {...base} advisorLede="" advisorBody="" defaultView="advisor" />);
    expect(screen.getByTestId("advisor-absent")).toBeInTheDocument();
  });

  it("renders the snapshot's advisor prose verbatim when present", () => {
    render(<AdvisorNote {...base} advisorLede="Frozen lede." advisorBody="Frozen body." defaultView="advisor" />);
    expect(screen.getByText("Frozen lede.")).toBeInTheDocument();
    expect(screen.getByText("Frozen body.")).toBeInTheDocument();
    expect(screen.queryByTestId("advisor-absent")).not.toBeInTheDocument();
  });
});
