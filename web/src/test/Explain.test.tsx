/**
 * Explainability tests — InfoButton open/close, ExplainPanel renders
 * formula sentence, VCI components, and narrative provenance badge.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { InfoButton } from "../report/InfoButton";

// ── Fixtures ──────────────────────────────────────────────────

const SCORE_EXPLAIN = {
  label: "Regulatory Exposure",
  score: 47.2,
  formula_version: "F-002_v1",
  formula_plain:
    "Sum of (Jurisdiction Weight x Regulator Priority Weight x " +
    "Disclosure Severity x Enforcement Frequency Weight) across all " +
    "regulators and domains, normalized to 0-100.",
  inputs: {
    domains_scored: ["data_sharing", "tracking_cookies"],
    total_clauses: 41,
    raw_sum: 2.34,
    max_possible: 5.0,
  },
  confidence: {
    vci: 52.0,
    label: "moderate",
    guidance: "Include with confidence caveat",
    components: { nlp: 0.6, benchmark: 0.4, regulatory: 0.5, enforcement: 0.3, source: 0.7 },
  },
  source_refs: { notice_id: "notice-001", clause_count: 41 },
};

const FINDING_EXPLAIN = {
  title: "Finding AI-004",
  domain: "ai_automated_decisions",
  severity: "high",
  score: 62.0,
  how_selected:
    "Selected from the fixed finding-type catalog because the " +
    "ai automated decisions domain had clauses AND maturity < 70. " +
    "The model did NOT invent this finding.",
  triggering_clause_ids: ["c1", "c2", "c3"],
  formula_version: "F-002_v1",
};

const NARRATIVE_EXPLAIN = {
  text: "TestCo presents an overall privacy intelligence score of 62.5.",
  provenance:
    "Numbers were computed by the formula engine. " +
    "The wording was produced from a fixed template.",
  numbers_from: ["f010", "f011"],
  guardrail: "passed",
  llm_used: false,
};

// ── InfoButton open/close ──────────────────────────────────────

describe("InfoButton", () => {
  it("renders the info button", () => {
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Test" />);
    expect(screen.getByTestId("info-button")).toBeInTheDocument();
  });

  it("opens ExplainPanel on click", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Test Score" />);
    expect(screen.queryByTestId("explain-panel")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("info-button"));
    expect(screen.getByTestId("explain-panel")).toBeInTheDocument();
  });

  it("closes ExplainPanel when close button clicked", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Test Score" />);

    await user.click(screen.getByTestId("info-button"));
    expect(screen.getByTestId("explain-panel")).toBeInTheDocument();

    await user.click(screen.getByTestId("explain-close"));
    expect(screen.queryByTestId("explain-panel")).not.toBeInTheDocument();
  });
});

// ── Score explanation ────────────────────────────────────────

describe("ExplainPanel — score", () => {
  it("renders the formula sentence", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Regulatory Exposure" />);
    await user.click(screen.getByTestId("info-button"));

    const panel = screen.getByTestId("explain-panel");
    const formulaSentence = within(panel).getByTestId("formula-sentence");
    expect(formulaSentence.textContent).toContain("Jurisdiction Weight");
    expect(formulaSentence.textContent).toContain("normalized to 0-100");
  });

  it("renders the formula version", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Regulatory Exposure" />);
    await user.click(screen.getByTestId("info-button"));

    expect(screen.getByText(/F-002_v1/)).toBeInTheDocument();
  });

  it("renders the inputs table", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Regulatory Exposure" />);
    await user.click(screen.getByTestId("info-button"));

    const table = screen.getByTestId("inputs-table");
    expect(table).toBeInTheDocument();
    expect(table.textContent).toContain("total clauses");
    expect(table.textContent).toContain("41");
  });

  it("renders VCI components as bars", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Regulatory Exposure" />);
    await user.click(screen.getByTestId("info-button"));

    expect(screen.getByTestId("vci-components")).toBeInTheDocument();
  });

  it("shows VCI score and guidance", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={SCORE_EXPLAIN} kind="score" label="Regulatory Exposure" />);
    await user.click(screen.getByTestId("info-button"));

    const panel = screen.getByTestId("explain-panel");
    expect(panel.textContent).toContain("52");
    expect(panel.textContent).toContain("moderate");
    expect(panel.textContent).toContain("Include with confidence caveat");
  });
});

// ── Finding explanation ──────────────────────────────────────

describe("ExplainPanel — finding", () => {
  it("renders how_selected text", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={FINDING_EXPLAIN} kind="finding" label="AI-004" />);
    await user.click(screen.getByTestId("info-button"));

    const howSelected = screen.getByTestId("how-selected");
    expect(howSelected.textContent).toContain("fixed finding-type catalog");
    expect(howSelected.textContent).toContain("model did NOT invent");
  });

  it("shows triggering clause count", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={FINDING_EXPLAIN} kind="finding" label="AI-004" />);
    await user.click(screen.getByTestId("info-button"));

    expect(screen.getByTestId("explain-panel").textContent).toContain("3 clause(s)");
  });
});

// ── Narrative explanation ─────────────────────────────────────

describe("ExplainPanel — narrative", () => {
  it("renders the provenance sentence", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={NARRATIVE_EXPLAIN} kind="narrative" label="Executive Summary" />);
    await user.click(screen.getByTestId("info-button"));

    const prov = screen.getByTestId("narrative-provenance");
    expect(prov.textContent).toContain("formula engine");
    expect(prov.textContent).toContain("fixed template");
  });

  it("shows guardrail badge as passed", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={NARRATIVE_EXPLAIN} kind="narrative" label="Executive Summary" />);
    await user.click(screen.getByTestId("info-button"));

    const badge = screen.getByTestId("guardrail-badge");
    expect(badge.textContent).toContain("passed");
  });

  it("shows LLM badge as template used", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={NARRATIVE_EXPLAIN} kind="narrative" label="Executive Summary" />);
    await user.click(screen.getByTestId("info-button"));

    const badge = screen.getByTestId("llm-badge");
    expect(badge.textContent).toContain("Template used");
  });

  it("shows LLM badge as rephrased when llm_used=true", async () => {
    const user = userEvent.setup();
    const llmExplain = { ...NARRATIVE_EXPLAIN, llm_used: true };
    render(<InfoButton explanation={llmExplain} kind="narrative" label="Executive Summary" />);
    await user.click(screen.getByTestId("info-button"));

    const badge = screen.getByTestId("llm-badge");
    expect(badge.textContent).toContain("LLM rephrased");
  });

  it("shows which formulas produced the numbers", async () => {
    const user = userEvent.setup();
    render(<InfoButton explanation={NARRATIVE_EXPLAIN} kind="narrative" label="Executive Summary" />);
    await user.click(screen.getByTestId("info-button"));

    const panel = screen.getByTestId("explain-panel");
    expect(panel.textContent).toContain("F010");
    expect(panel.textContent).toContain("F011");
  });
});
