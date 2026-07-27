/**
 * Report rendering tests — all 12 sections from fixture payload,
 * no banned terms, honest cohort label, draft banner.
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

// Banned terms that must never appear in generated prose
const BANNED_TERMS = [
  "violation", "violates", "illegal", "unlawful",
  "non-compliant", "noncompliant", "breach of law",
  "guilty", "liable",
];

const FIXTURE: ReportPayload = {
  assessment_id: "test-assess-001",
  organization_name: "TestCo",
  generated_date: "2026-07-18",
  cohort_size: 23,
  cohort_date: "2026-07-18",
  vci_label: "moderate",
  sections: [
    { number: 1, title: "Cover", content: {
      organization: "TestCo", report_title: "Privacy Intelligence Assessment",
      date: "2026-07-18", overall_score: 62.5, vci_label: "moderate", snapshot_id: "snap-001",
    }},
    { number: 2, title: "Executive Summary", content: {
      summary: "TestCo presents an overall privacy intelligence score of 62.5 out of 100.",
      takeaways: ["Data sharing exposure is elevated.", "Retention periods need clarification."],
      overall_score: 62.5, finding_count: 2, cohort_size: 23, cohort_date: "2026-07-18",
    }},
    { number: 3, title: "Risk Dashboard", content: {
      overall_intelligence: 62.5, regulatory_exposure: 45, regulatory_tier: "moderate",
      disclosure_maturity: 78, transparency: 35, ai_transparency: 42, compound_risk: 28,
      vci_score: 58, vci_label: "moderate",
    }},
    { number: 4, title: "Benchmark Intelligence", content: {
      org_score: 62.5, percentile: 71, cohort_size: 23, cohort_date: "2026-07-18",
      cohort_label: "n=23 peers as of 2026-07-18", benchmark_deviation: 15,
    }},
    { number: 5, title: "Regulator Exposure", content: {
      regulatory_score: 45, tier: "moderate", heatmap: [], lineage: {},
    }},
    { number: 6, title: "Disclosure Findings", content: {
      findings: [
        { id: "SH-002", domain: "data_sharing", severity: "high", score: 65, confidence: "moderate" },
        { id: "RT-003", domain: "retention", severity: "medium", score: 45, confidence: "moderate" },
      ],
      total: 2,
    }},
    { number: 7, title: "Compound Risk Analysis", content: { compound_score: 28, lineage: {} }},
    { number: 8, title: "Benchmark Language Comparison", content: {
      sme_cleaned_available: false,
      entries: [{ domain: "pending", exemplar_text: "Pending SME-cleaned exemplar", maturity_note: "" }],
    }},
    { number: 9, title: "Strategic Recommendations", content: {
      recommendations: [
        { severity: "high", code: "SH-002", title: "Clarify Sharing", prose: "Review data sharing practices." },
      ],
    }},
    { number: 10, title: "Risk Reduction Priorities", content: { high_count: 1, medium_count: 1 }},
    { number: 11, title: "Source Traceability", content: {
      note: "All scores traceable via snapshot snap-001. Benchmarked against 23 peers as of 2026-07-18.",
    }},
    { number: 12, title: "Trend & Emerging Risk", content: {
      note: "Per-company trend analysis requires monitoring history.",
    }},
  ],
};

describe("ReportView", () => {
  it("renders all 12 sections", () => {
    renderReport(FIXTURE);
    for (let i = 1; i <= 12; i++) {
      expect(screen.getByTestId(`section-${i}`)).toBeInTheDocument();
    }
  });

  it("shows organization name in cover", () => {
    renderReport(FIXTURE);
    expect(screen.getByText("TestCo")).toBeInTheDocument();
  });

  it("shows overall score", () => {
    renderReport(FIXTURE);
    expect(screen.getAllByText("62.5").length).toBeGreaterThan(0);
  });

  it("shows VCI badge", () => {
    renderReport(FIXTURE);
    const badges = screen.getAllByTestId("vci-badge");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("shows honest cohort label with real n and date", () => {
    renderReport(FIXTURE);
    const labels = screen.getAllByTestId("cohort-label");
    expect(labels.length).toBeGreaterThan(0);
    expect(labels[0].textContent).toContain("23");
    expect(labels[0].textContent).toContain("2026");
  });

  it("does not show fabricated cohort sizes", () => {
    renderReport(FIXTURE);
    const html = document.body.innerHTML;
    expect(html).not.toContain("1,250");
    expect(html).not.toContain("1250+");
    expect(html).not.toContain("10,000");
  });

  it("shows exemplar placeholder when sme_cleaned=false", () => {
    renderReport(FIXTURE);
    expect(screen.getByTestId("exemplar-placeholder")).toBeInTheDocument();
    expect(screen.getByText(/Pending SME-reviewed/)).toBeInTheDocument();
  });

  it("shows findings table", () => {
    renderReport(FIXTURE);
    expect(screen.getAllByText("SH-002").length).toBeGreaterThan(0);
    expect(screen.getAllByText("RT-003").length).toBeGreaterThan(0);
  });

  it("contains no banned terms", () => {
    renderReport(FIXTURE);
    const html = document.body.innerHTML.toLowerCase();
    for (const term of BANNED_TERMS) {
      expect(html).not.toContain(term);
    }
  });

  it("shows draft banner when present", () => {
    const draft = { ...FIXTURE, draft_banner: "DRAFT — pending expert review" };
    renderReport(draft);
    expect(screen.getAllByRole("status", { name: /Report status: draft/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Draft — Pending Review/i).length).toBeGreaterThan(0);
  });

  it("hides draft banner when not present", () => {
    renderReport(FIXTURE);
    expect(screen.getAllByRole("status", { name: /Report status: approved/i }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Draft — Pending Review/i)).not.toBeInTheDocument();
  });

  it("shows takeaways in executive summary", () => {
    renderReport(FIXTURE);
    expect(screen.getByText("Data sharing exposure is elevated.")).toBeInTheDocument();
  });

  it("shows recommendations", () => {
    renderReport(FIXTURE);
    expect(screen.getByText(/Review data sharing practices/)).toBeInTheDocument();
  });

  it("renders the report container with testid", () => {
    renderReport(FIXTURE);
    expect(screen.getByTestId("report-view")).toBeInTheDocument();
  });
});
