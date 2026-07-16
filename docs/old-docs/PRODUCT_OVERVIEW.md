# Visentix Privacy Intelligence Platform — Product & Feature Overview

Visentix turns public privacy notices into benchmark-driven privacy **INTELLIGENCE**. It maps notice clauses, benchmarks organizations against peer cohorts, and exposes maturity and risk findings without making legal verdicts.

---

## 1. Product Philosophy & Design Guardrails

Visentix follows a strict, non-negotiable set of product rules to ensure the integrity, reproducibility, and safety of its intelligence output:

*   **Intelligence, Not Compliance:** The platform never declares whether an organization or notice is "compliant," "legal," or "illegal." All findings and metrics are phrased in terms of *exposure*, *maturity*, *likelihood*, *benchmarks*, and *confidence*.
*   **Phrasing Guardrail:** A hard guardrail runs at report-drafting time. Banned legal-verdict terms—including `"violation"`, `"violates"`, `"illegal"`, `"unlawful"`, `"non-compliant"`, `"breach of law"`, `"guilty"`, and `"liable"`—are strictly blocked. Any attempt to output these terms will raise a `GuardrailError` and halt report compilation.
*   **Honest Numbers:** The platform reports exact, uninflated peer cohort sizes (e.g., `n=30 peers as of 2026-06-19`) and attaches a low-confidence rating if the cohort size is too small. Text such as "1,250+" or fabricated metrics are strictly prohibited.
*   **No Score Without Lineage:** Every computed score stored in the database includes its source lineage: the formula version ID, input reference IDs (clauses, obligations, regulators, etc.), a Visentix Confidence Index (VCI) score, and a generation timestamp.
*   **Reproducibility:** Reports are frozen into database snapshots (`report_snapshot` table) upon publication. Re-scoring or re-running algorithms creates a new versioned row, preserving historical snapshots so past reports can always be regenerated identically.

---

## 2. Ingestion & Intake Pipeline

The front door of Visentix takes raw privacy notices and structures them for processing:

1.  **Ingestion Formats:** Users can submit notices via:
    *   **URL Ingestion:** Features built-in SSRF (Server-Side Request Forgery) protection to block requests to private, loopback, link-local, or cloud metadata endpoints.
    *   **PDF Upload:** PyMuPDF-based parser designed for defensive extraction without shell-outs to untrusted systems.
    *   **Raw Text Input:** Direct copy-paste into the text box.
2.  **Structural Decomposing:** The parser splits the extracted document into `notice_section` blocks (retaining title and sequence) and further into individual `disclosure_clause` rows.
3.  **NLP & LLM Classification:** Clauses are mapped to the 8 core taxonomy domains plus an `other` category:
    *   `data_sharing`
    *   `tracking_cookies`
    *   `consumer_rights`
    *   `cross_border`
    *   `sensitive_data`
    *   `retention`
    *   `children_teens`
    *   `ai_automated_decisions`
    *   `other`
    *   *Classification Strategy:* Leverages a local LLM client (Ollama Qwen3:8b) and OpenAI-compatible APIs to run domain classification, with an automated regex-based keyword pattern fallback in case the LLM is unresponsive.

---

## 3. Scoring & Normalization Engine

Visentix calculates 14 versioned formulas (`F-001` through `F-014`) to evaluate risk exposure:

*   **F-001 — Source Reliability Score:** Evaluates source records based on authority weight, freshness weight, completeness weight, and extraction confidence.
*   **F-002 — Regulatory Exposure Score:** Multiplies Jurisdiction Weights (JW) by Regulator Priority Weights (RPW) and Disclosure Severity (DS) per domain.
*   **F-003 — Benchmark Deviation Score:** Quantifies deviation between an organization's score and the top quartile of its weighted peer cohort.
*   **F-004 — Enforcement Correlation Score:** Models the overlap of an organization's disclosure clauses with historical enforcement actions using cosine similarity.
*   **F-005 — Disclosure Maturity Score:** Scores the presence of required disclosure elements mapped from the master checklist (`config/element_checklist.csv`).
*   **F-006 — Transparency Score:** A composite score reflecting readability, clarity, and completeness.
*   **F-007 — AI Transparency Maturity:** Evaluates the specificity of disclosures regarding automated decision-making and artificial intelligence.
*   **F-008 — Compound Risk Score:** Blends regulatory, disclosure, and enforcement dimensions into a single indicator.
*   **F-009 — Confidence Weighted Score:** Adjusts risk metrics based on source reliability.
*   **F-010 — Overall Privacy Intelligence Score:** A weighted combination of all risk dimensions (Regulatory, Benchmark, Disclosure, Enforcement, AI, and Compound).
*   **F-011 — Benchmark Percentile:** The organization's rank relative to the peer cohort.
*   **F-012 — Trend Delta:** The temporal shift in score over time, reporting `"no_prior_history"` for first assessments.
*   **F-013 — Alert Escalation:** Triggers alerts when scores drop or significant changes occur.
*   **F-014 — Report Confidence Index:** Refined confidence rating (VCI).

### Profile & Normalization
*   **Organization Intelligence Profile:** Aggregates scores across 7 dimensions (`ic`, `rss`, `pgms`, `osi`, `dsi`, `ehp`, `aigms`).
*   **Normalization Engine:** Utilizes similarity weights to construct customized benchmark peer cohorts for comparison, ensuring comparisons are relative and statistically valid.

---

## 4. 12-Section Interactive Report

Reports are rendered via React on the frontend and are also exportable to PDF (via WeasyPrint). The report is structured into 12 distinct sections:

1.  **Cover Page:** Displays the organization name, metadata (industry, size, geography, domain), overall Privacy Intelligence Score, and the VCI confidence rating.
2.  **Executive Summary:** A prose overview of the assessment generated by the narrative engine (with strict number verification to prevent LLM hallucinations) and key takeaways.
3.  **Risk Dashboard:** A chart dashboard utilizing Recharts to show score indicators across all major dimensions (Overall, Regulatory, Disclosure, Transparency, AI, and Compound).
4.  **Benchmark Intelligence:** Compares the organization's score and percentile relative to the cohort size.
5.  **Regulator Exposure Heatmap:** A visual 9x8 grid mapping active regulatory entities (e.g., FTC, CPPA) across the 8 privacy domains, indicating where enforcement frequency and regulator priority intersect.
6.  **Disclosure Findings Table:** Highlights identified exposure events referencing codes from the fixed `finding_type` catalog (e.g., `SH-002`, `RT-003`).
7.  **Compound Risk Analysis:** Deep dive into compound risk scores and mathematical lineages.
8.  **Benchmark Language Comparison:** Compares organization clauses side-by-side with SME-cleaned exemplar clauses representing mature or high-risk language.
9.  **Strategic Recommendations:** Actionable remediation suggestions mapped from the `recommendation_library` with filled template variables.
10. **Risk Reduction Priorities:** Prioritizes recommendations categorized by High and Medium severity.
11. **Source Traceability:** Displays the exact audit trail, including formula versions used and snapshot IDs, to guarantee reproducibility.
12. **Trend & Emerging Risk:** Captures scores over time and shifts in the regulatory landscape.

---

## 5. Subject Matter Expert (SME) Review Gate

A human-in-the-loop review gate controls report lifecycle states before they become client-visible:

*   **Review Status Flow:** `draft` $\rightarrow$ `in_review` $\rightarrow$ `approved`.
*   **Finding Actions:** SMEs review the auto-generated findings and can **Confirm**, **Edit** (modify title/description), or **Dismiss** a finding. Dismissed findings are removed from the client-facing report.
*   **Exemplar Cleaning:** Candidates for the exemplar library can be cleaned by SMEs to remove identifying organization/personal details. The platform runs a de-identification regex checker to block approval if names, emails, URLs, or custom tokens remain.
*   **Training Label Capture:** Every decision made by an SME (Confirm/Edit/Dismiss) is captured as a structured training label and stored in the database. This builds a feedback loop for fine-tuning future NLP models.
*   **Flexible Gate Modes:**
    *   `strict`: Customers see nothing until the report is explicitly SME-approved.
    *   `instant_draft` (Default): Customers see the draft report immediately with a yellow warning banner.
    *   `client_reviews`: Customers can access the draft report and leave comments.

---

## 6. Access Control & Platform Security

*   **Role-Based Access Control:** Role-based routing enforces separation between:
    *   `customer`: Can submit notice assessments, view their organization's dashboard, and read approved reports (or drafts depending on the Gate Mode).
    *   `sme`: Accesses the SME Review Queue, manages finding actions, cleans exemplars, and approves reports.
    *   `admin`: Accesses the Admin Console, checks API health and database counts, monitors training statistics, and changes global gate mode settings.
*   **Row Level Security (RLS):** Enabled in Supabase on customer-facing tables to restrict data access to authorised users only.
*   **Token Verification:** All requests to backend endpoints verify Supabase JWT signatures (HS256) and restrict routes to allowed user roles.
