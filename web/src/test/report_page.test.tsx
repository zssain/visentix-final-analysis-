/**
 * ReportPage tests — renders 12 sections from fixture, no client-side recompute,
 * DRAFT banner, honest cohort, no banned terms.
 *
 * Uses ReportView directly (same component as Playwright PDF) with fixture data.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExplainProvider } from "../report/explain/ExplainContext";
import { ReportView } from "../report/ReportView";
import type { ReportPayload } from "../report/types";

function renderReport(report: ReportPayload) {
  return render(
    <ExplainProvider>
      <ReportView report={report} />
    </ExplainProvider>
  );
}

const BANNED_TERMS = [
  "violation", "violates", "illegal", "unlawful",
  "non-compliant", "noncompliant", "breach of law",
  "guilty", "liable",
];

const FIXTURE: ReportPayload = {
  assessment_id: "rp-test-001",
  organization_name: "ReportTestCo",
  generated_date: "2026-06-29",
  cohort_size: 30,
  cohort_date: "2026-06-29",
  vci_label: "high",
  sections: [
    { number: 1, title: "Cover", content: {
      organization: "ReportTestCo", report_title: "Privacy Intelligence Assessment",
      date: "2026-06-29", overall_score: 68.5, vci_label: "high", snapshot_id: "snap-rp",
    }},
    { number: 2, title: "Executive Summary", content: {
      summary: "ReportTestCo presents an overall score of 68.5 out of 100.",
      takeaways: ["Data sharing exposure elevated."], cohort_size: 30, cohort_date: "2026-06-29",
    }},
    { number: 3, title: "Risk Dashboard", content: {
      overall_intelligence: 68.5, regulatory_exposure: 42, regulatory_tier: "moderate",
      disclosure_maturity: 75, transparency: 38, ai_transparency: 50, compound_risk: 22,
      vci_score: 62, vci_label: "high",
    }},
    { number: 4, title: "Benchmark Intelligence", content: {
      org_score: 68.5, percentile: 74, cohort_size: 30, cohort_date: "2026-06-29",
      cohort_label: "n=30 peers as of 2026-06-29",
    }},
    { number: 5, title: "Regulator Exposure", content: { regulatory_score: 42, tier: "moderate" }},
    { number: 6, title: "Disclosure Findings", content: {
      findings: [{ id: "SH-002", domain: "data_sharing", severity: "high", score: 60, confidence: "high" }],
      total: 1,
    }},
    { number: 7, title: "Compound Risk Analysis", content: { compound_score: 22 }},
    { number: 8, title: "Benchmark Language Comparison", content: {
      sme_cleaned_available: true,
      entries: [{ domain: "data_sharing", exemplar_text: "De-identified sharing exemplar.", maturity_note: "High." }],
    }},
    { number: 9, title: "Strategic Recommendations", content: {
      recommendations: [{ severity: "high", code: "SH-002", title: "Clarify", prose: "Review sharing disclosures." }],
    }},
    { number: 10, title: "Risk Reduction Priorities", content: { high_count: 1, medium_count: 0 }},
    { number: 11, title: "Source Traceability", content: { note: "Traceable via snapshot snap-rp. 30 peers as of 2026-06-29." }},
    { number: 12, title: "Trend & Emerging Risk", content: { note: "Trend requires monitoring history." }},
  ],
};

describe("ReportPage / ReportView", () => {
  it("renders all 12 sections", () => {
    renderReport(FIXTURE);
    for (let i = 1; i <= 12; i++) {
      expect(screen.getByTestId(`section-${i}`)).toBeInTheDocument();
    }
  });

  it("displays the stored payload (no client-side recompute)", () => {
    renderReport(FIXTURE);
    // The score 68.5 comes from the fixture, not computed in the browser
    expect(screen.getAllByText("68.5").length).toBeGreaterThan(0);
    expect(screen.getByText("ReportTestCo")).toBeInTheDocument();
  });

  it("shows DRAFT banner when flagged", () => {
    const draft = { ...FIXTURE, draft_banner: "DRAFT — pending expert review" };
    renderReport(draft);
    expect(screen.getAllByRole("status", { name: /Report status: draft/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Draft — Pending Review/i).length).toBeGreaterThan(0);
  });

  it("hides banner when not flagged", () => {
    renderReport(FIXTURE);
    expect(screen.getAllByRole("status", { name: /Report status: approved/i }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Draft — Pending Review/i)).not.toBeInTheDocument();
  });

  it("shows honest cohort label with real n and date", () => {
    renderReport(FIXTURE);
    const labels = screen.getAllByTestId("cohort-label");
    expect(labels.length).toBeGreaterThan(0);
    expect(labels[0].textContent).toContain("30");
    expect(labels[0].textContent).toContain("2026");
  });

  it("does not show fabricated cohort sizes", () => {
    renderReport(FIXTURE);
    const html = document.body.innerHTML;
    expect(html).not.toContain("1,250");
    expect(html).not.toContain("1250+");
  });

  it("contains no banned terms", () => {
    renderReport(FIXTURE);
    const html = document.body.innerHTML.toLowerCase();
    for (const term of BANNED_TERMS) {
      expect(html).not.toContain(term);
    }
  });

  it("shows cleaned exemplar in Section 8 (not placeholder)", () => {
    renderReport(FIXTURE);
    expect(screen.getByText("De-identified sharing exemplar.")).toBeInTheDocument();
    expect(screen.queryByTestId("exemplar-placeholder")).not.toBeInTheDocument();
  });

  it("is the same component used for PDF (ReportView)", () => {
    // This test confirms portal and PDF use the same component
    const { container } = renderReport(FIXTURE);
    expect(container.querySelector("[data-testid='report-view']")).toBeInTheDocument();
  });
});
