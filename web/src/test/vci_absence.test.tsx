/**
 * DATA-003: a fabricated confidence value (75) must never be rendered as if real.
 * When a real VCI/confidence is absent, the report sections render honest absence
 * ("—" / "Not recorded") and NEVER the fabricated "75".
 */
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RegulatorExposure } from "../report/sections/RegulatorExposure";
import { FindingsTable } from "../report/sections/FindingsTable";
import { AdvisorNote } from "../components/AdvisorNote";

afterEach(cleanup);

describe("RegulatorExposure — VCI honest absence (DATA-003)", () => {
  it("does not render a fabricated 75 when vci_score is absent", () => {
    const { container } = render(
      <RegulatorExposure content={{ regulatory_score: 42, tier: "elevated", regulators: [] }} />
    );
    expect(container.textContent).not.toContain("75");
  });

  it("opens the lineage drawer and shows honest absence (—) for VCI when absent", () => {
    render(
      <RegulatorExposure content={{ regulatory_score: 42, tier: "elevated", regulators: [] }} />
    );
    fireEvent.click(screen.getByLabelText(/click to view score lineage/i));
    const vciLabel = screen.getByText("VCI Score");
    const valueEl = vciLabel.parentElement?.querySelector(".lm-value");
    expect(valueEl?.textContent).toBe("—");
    expect(valueEl?.textContent).not.toContain("75");
  });

  it("renders the real vci_score when present", () => {
    render(
      <RegulatorExposure content={{ regulatory_score: 42, tier: "elevated", regulators: [], vci_score: 88 }} />
    );
    fireEvent.click(screen.getByLabelText(/click to view score lineage/i));
    const vciLabel = screen.getByText("VCI Score");
    const valueEl = vciLabel.parentElement?.querySelector(".lm-value");
    expect(valueEl?.textContent).toBe("88");
  });
});

describe("FindingsTable — confidence honest absence (DATA-003)", () => {
  const findingBase = {
    id: "SH-002",
    domain: "data_sharing",
    severity: "elevated",
    score: 60,
    finding_code: "SH-002",
  };

  it("shows 'Not recorded' and never 75 when confidence is absent", () => {
    const { container } = render(
      <FindingsTable content={{ total: 1, findings: [{ ...findingBase, confidence: "" }] }} />
    );
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
    expect(container.textContent).not.toContain("75");
  });

  it("renders the real confidence when present", () => {
    render(
      <FindingsTable content={{ total: 1, findings: [{ ...findingBase, confidence: "62%" }] }} />
    );
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.queryByText("Not recorded")).not.toBeInTheDocument();
  });
});

describe("AdvisorNote — VCI honest absence (DATA-003)", () => {
  const base = {
    findingCode: "SH-002", title: "t", domain: "data_sharing",
    status: "approved" as const, snapshotId: "snap-1",
    exposureScore: 60, cohortPercentile: 70,
    formulaId: "F-002", formulaDesc: "desc", cohortSize: 25, cohortDate: "2026-07-20",
    advisorLede: "", advisorBody: "",
  };

  it("renders 'Not recorded' for VCI when absent (analyst view)", () => {
    render(<AdvisorNote {...base} vci={undefined} defaultView="analyst" />);
    expect(screen.getByTestId("advisor-vci").textContent).toBe("Not recorded");
  });

  it("renders the real VCI when present", () => {
    render(<AdvisorNote {...base} vci={62} defaultView="analyst" />);
    expect(screen.getByTestId("advisor-vci").textContent).toBe("62%");
  });
});
