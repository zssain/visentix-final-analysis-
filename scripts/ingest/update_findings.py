"""Update all 8 finding_type stubs with audit-quality content and link to legal refs.

Replaces STUB titles/body_templates with professional, exposure/maturity language.
Inserts finding_legal_reference rows linking findings to real legal_reference rows.

Idempotent: PATCHes overwrite; finding_legal_reference uses upsert on PK.

Prerequisites:
    - Apply db/migrations/0012_finding_content.sql first (adds definition column).
    - legal_reference table populated (run ingest_legal_refs.py).

Usage:
    PYTHONPATH=. python scripts/ingest/update_findings.py
"""

import logging

import httpx

from scripts.ingest._common import (
    H,
    URL,
    finish_run,
    start_run,
    upsert,
)

log = logging.getLogger("ingest.update_findings")

# ────────────────────────────────────────────────────────────
# 1. Finding type updates — titles + definitions
# ────────────────────────────────────────────────────────────

FINDING_TYPES = {
    "CR-001": {
        "title": "Consumer Rights Disclosure Gap",
        "definition": (
            "The privacy notice does not adequately describe one or more consumer "
            "rights — such as the right to access, delete, correct, or opt out of "
            "the sale or sharing of personal information — as expected under "
            "applicable privacy frameworks."
        ),
    },
    "SH-002": {
        "title": "Data Sharing Transparency Exposure",
        "definition": (
            "The privacy notice does not sufficiently disclose the categories of "
            "third parties with whom personal information is shared, the purposes "
            "of sharing, or the consumer's ability to limit such sharing."
        ),
    },
    "RT-003": {
        "title": "Retention Period Disclosure Omission",
        "definition": (
            "The privacy notice omits or provides only vague descriptions of data "
            "retention periods, failing to specify how long each category of personal "
            "information is retained and the criteria used to determine those periods."
        ),
    },
    "AI-004": {
        "title": "Automated Decision-Making Transparency Gap",
        "definition": (
            "The privacy notice does not adequately disclose the use of automated "
            "decision-making or profiling technologies, the logic involved, or "
            "the significance and anticipated consequences for data subjects."
        ),
    },
    "DC-005": {
        "title": "Privacy Notice Completeness Deficiency",
        "definition": (
            "The privacy notice is missing one or more required disclosure elements "
            "— such as categories of data collected, purposes of processing, or "
            "contact information — resulting in an incomplete notice that may not "
            "meet regulatory expectations."
        ),
    },
    "SEC-002": {
        "title": "Sensitive Data Handling Exposure",
        "definition": (
            "The privacy notice does not adequately address the collection, use, "
            "or safeguarding of sensitive personal information — including health, "
            "biometric, financial, or precise geolocation data — or does not "
            "disclose the consumer's right to limit such processing."
        ),
    },
    "TRK-007": {
        "title": "Tracking Technology Disclosure Weakness",
        "definition": (
            "The privacy notice provides insufficient detail about the tracking "
            "technologies deployed (cookies, pixels, device fingerprinting), their "
            "purposes, or the mechanisms available for consumers to manage consent."
        ),
    },
    "XB-001": {
        "title": "Cross-Border Transfer Safeguard Gap",
        "definition": (
            "The privacy notice does not adequately describe international data "
            "transfers, the destination countries or regions involved, or the "
            "legal mechanisms and safeguards in place to protect transferred data."
        ),
    },
}

# ────────────────────────────────────────────────────────────
# 2. Recommendation library updates — body_templates
# ────────────────────────────────────────────────────────────

RECOMMENDATIONS = {
    "CR-001": {
        "title": "Strengthen Consumer Rights Disclosures",
        "body_template": (
            "The organization's privacy notice should clearly enumerate each consumer "
            "right available under applicable law — including the rights to access, "
            "delete, correct, and port personal information, as well as the right to "
            "opt out of sale or sharing. For each right, the notice should describe: "
            "(1) how consumers can submit a request ({consumer_rights}), "
            "(2) the verification process, (3) expected response timelines, and "
            "(4) any limitations. Organizations with higher maturity profiles "
            "typically provide a centralized rights-request portal and publish "
            "response-time metrics."
        ),
        "source_note": "CCPA/CPRA §§1798.100-120; GDPR Arts. 15-21; VCDPA §59.1-577",
    },
    "SH-002": {
        "title": "Enhance Data Sharing Transparency",
        "body_template": (
            "The privacy notice should identify the categories of third parties "
            "receiving personal information, the specific purposes for each sharing "
            "arrangement, and whether such sharing constitutes a 'sale' or 'sharing' "
            "under applicable law. For each category of recipient "
            "({third_party_categories}), disclose: (1) the types of data shared, "
            "(2) the legal basis or business purpose, (3) contractual safeguards "
            "in place, and (4) the consumer's opt-out mechanism. Organizations "
            "demonstrating mature practices maintain a public vendor registry "
            "or data-flow map."
        ),
        "source_note": "CCPA/CPRA §1798.120; GDPR Art. 13(1)(e); GLBA §313.6",
    },
    "RT-003": {
        "title": "Specify Data Retention Periods",
        "body_template": (
            "The privacy notice should state, for each category of personal "
            "information ({data_categories}), the specific retention period or "
            "the criteria used to determine it. Where retention varies by purpose "
            "or legal obligation, each basis should be disclosed separately. "
            "Best-practice notices include a retention schedule table mapping data "
            "categories to retention periods, legal bases, and deletion procedures. "
            "Vague language such as 'as long as necessary' without further context "
            "represents an elevated exposure area."
        ),
        "source_note": "CCPA/CPRA §1798.100(a)(3); GDPR Art. 5(1)(e); CPPA Regulations §7002",
    },
    "AI-004": {
        "title": "Disclose Automated Decision-Making Practices",
        "body_template": (
            "The privacy notice should disclose whether the organization uses "
            "automated decision-making or profiling that produces legal or "
            "similarly significant effects. For each use case ({ai_use_cases}), "
            "the notice should describe: (1) the categories of data used as inputs, "
            "(2) the general logic involved, (3) the significance and anticipated "
            "consequences for the individual, and (4) the right to opt out or "
            "request human review. Organizations with mature AI governance "
            "programs publish model cards or algorithmic impact assessments."
        ),
        "source_note": "CPRA ADMT Regulations; GDPR Art. 22; Colorado CPA §6-1-1303(a)(I)(C)",
    },
    "DC-005": {
        "title": "Address Privacy Notice Completeness Gaps",
        "body_template": (
            "The privacy notice should be reviewed to ensure all required disclosure "
            "elements are present, including: categories of personal information "
            "collected, purposes of processing, categories of sources, categories "
            "of third-party recipients, consumer rights, and contact information. "
            "The following elements require attention: {missing_elements}. "
            "A complete notice reduces regulatory inquiry exposure and aligns with "
            "maturity benchmarks for the organization's industry and size profile."
        ),
        "source_note": "CCPA/CPRA §1798.100(a)-(b); GDPR Art. 13; FTC Act §5 (transparency)",
    },
    "SEC-002": {
        "title": "Strengthen Sensitive Data Safeguard Disclosures",
        "body_template": (
            "The privacy notice should explicitly identify each category of sensitive "
            "personal information collected ({sensitive_data_types}) and disclose: "
            "(1) the specific purposes for which sensitive data is processed, "
            "(2) the legal basis or consent mechanism, (3) the consumer's right to "
            "limit the use of sensitive information, and (4) the technical and "
            "organizational safeguards applied. Where health, biometric, or "
            "financial data is involved, sector-specific frameworks may impose "
            "additional disclosure requirements beyond the general privacy law."
        ),
        "source_note": "CCPA/CPRA §1798.121; GDPR Art. 9; HIPAA §164.520; BIPA 740 ILCS 14/15",
    },
    "TRK-007": {
        "title": "Improve Tracking Technology Disclosures",
        "body_template": (
            "The privacy notice should enumerate the tracking technologies deployed "
            "({tracking_technologies}), including first-party and third-party "
            "cookies, pixels, SDKs, and device fingerprinting methods. For each "
            "technology, the notice should describe: (1) the purpose (analytics, "
            "advertising, personalization, fraud prevention), (2) the data collected, "
            "(3) the retention period, and (4) the consumer's ability to manage "
            "consent or opt out. A Global Privacy Control (GPC) signal-honoring "
            "mechanism is expected under CCPA/CPRA and several state laws."
        ),
        "source_note": "ePrivacy Directive Art. 5(3); FTC Act §5; CCPA/CPRA GPC requirements",
    },
    "XB-001": {
        "title": "Disclose Cross-Border Transfer Mechanisms",
        "body_template": (
            "The privacy notice should identify whether personal information is "
            "transferred outside the jurisdiction of collection and, if so, disclose: "
            "(1) the destination countries or regions ({destination_countries}), "
            "(2) the legal transfer mechanism relied upon (adequacy decision, "
            "standard contractual clauses, binding corporate rules, or derogation), "
            "(3) the safeguards applied, and (4) how consumers can obtain a copy "
            "of the safeguard documentation. Organizations with multinational "
            "operations should maintain a transfer impact assessment."
        ),
        "source_note": "GDPR Arts. 44-49; CCPA/CPRA (implied via service-provider contracts)",
    },
}

# ────────────────────────────────────────────────────────────
# 3. Finding → Legal Reference links
# ────────────────────────────────────────────────────────────

FINDING_LEGAL_REFS = [
    # CR-001 — Consumer Rights
    ("CR-001", "CCPA-CPRA", True, "CCPA/CPRA is the primary US comprehensive framework establishing consumer access, deletion, correction, and opt-out rights."),
    ("CR-001", "GDPR-ART-15", False, "GDPR Art. 15 provides the right of access for EU data subjects."),
    ("CR-001", "GDPR-ART-17", False, "GDPR Art. 17 establishes the right to erasure (right to be forgotten)."),
    ("CR-001", "GDPR-ART-21", False, "GDPR Art. 21 provides the right to object to processing."),
    ("CR-001", "VCDPA-VA", False, "VCDPA grants Virginia consumers comparable access, correction, and deletion rights."),

    # SH-002 — Data Sharing
    ("SH-002", "CCPA-CPRA", True, "CCPA/CPRA requires disclosure of third-party sharing categories and provides the right to opt out of sale or sharing."),
    ("SH-002", "GDPR-ART-13", False, "GDPR Art. 13(1)(e) requires disclosure of recipients or categories of recipients of personal data."),
    ("SH-002", "GLBA-313.6", False, "GLBA §313.6 governs disclosure requirements for sharing nonpublic personal financial information."),

    # TRK-007 — Tracking
    ("TRK-007", "CCPA-CPRA", True, "CCPA/CPRA requires honoring Global Privacy Control signals and disclosure of tracking technologies that constitute sale or sharing."),
    ("TRK-007", "GDPR-ART-7", False, "GDPR Art. 7 establishes conditions for valid consent, applicable to cookie/tracking consent under the ePrivacy Directive."),

    # AI-004 — Automated Decisions
    ("AI-004", "GDPR-ART-22", True, "GDPR Art. 22 is the primary framework governing automated individual decision-making and the right to human review."),
    ("AI-004", "CCPA-CPRA", False, "CPRA ADMT regulations require disclosure and opt-out for automated decision-making technology."),
    ("AI-004", "GDPR-ART-35", False, "GDPR Art. 35 requires data protection impact assessments for high-risk automated processing."),
    ("AI-004", "CPA-CO", False, "Colorado CPA requires disclosure and opt-out of profiling in furtherance of decisions that produce legal or similarly significant effects."),

    # RT-003 — Retention
    ("RT-003", "CCPA-CPRA", True, "CCPA/CPRA §1798.100(a)(3) requires businesses to disclose the retention period for each category of personal information."),
    ("RT-003", "GDPR-ART-5", False, "GDPR Art. 5(1)(e) establishes the storage limitation principle requiring data to be kept no longer than necessary."),
    ("RT-003", "GDPR-ART-13", False, "GDPR Art. 13(2)(a) requires controllers to inform data subjects of retention periods or criteria."),

    # SEC-002 — Sensitive Data
    ("SEC-002", "CCPA-CPRA", True, "CCPA/CPRA §1798.121 provides the right to limit the use and disclosure of sensitive personal information."),
    ("SEC-002", "GDPR-ART-9", False, "GDPR Art. 9 governs processing of special categories of data including health, biometric, and racial data."),
    ("SEC-002", "HIPAA-164.520", False, "HIPAA §164.520 requires covered entities to provide a notice of privacy practices for protected health information."),
    ("SEC-002", "BIPA-IL", False, "Illinois BIPA requires written informed consent before collection of biometric identifiers and information."),

    # XB-001 — Cross-Border
    ("XB-001", "GDPR-ART-44", True, "GDPR Art. 44 establishes the general principle that international transfers require adequate safeguards."),
    ("XB-001", "GDPR-ART-46", False, "GDPR Art. 46 specifies appropriate safeguards including standard contractual clauses and binding corporate rules."),
    ("XB-001", "GDPR-ART-49", False, "GDPR Art. 49 provides derogations for specific situations where transfers may occur without adequacy or safeguards."),

    # DC-005 — Disclosure Completeness
    ("DC-005", "CCPA-CPRA", True, "CCPA/CPRA §1798.100(a)-(b) prescribes the required elements of a complete privacy notice at or before the point of collection."),
    ("DC-005", "GDPR-ART-13", False, "GDPR Art. 13 lists mandatory information to be provided when data is collected from the data subject."),
    ("DC-005", "GDPR-ART-14", False, "GDPR Art. 14 lists mandatory information when data has not been obtained directly from the data subject."),
]


def patch_row(table: str, filter_col: str, filter_val: str, payload: dict) -> bool:
    """PATCH a single row via PostgREST. Returns True on success."""
    headers = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}
    r = httpx.patch(
        f"{URL}/rest/v1/{table}?{filter_col}=eq.{filter_val}",
        headers=headers,
        json=payload,
        timeout=15,
    )
    if r.status_code < 300:
        return True
    log.warning("PATCH %s %s=%s → %d: %s", table, filter_col, filter_val, r.status_code, r.text[:200])
    return False


def check_column_exists(table: str, column: str) -> bool:
    """Check if a column is accessible via PostgREST."""
    headers = {**H}
    r = httpx.get(
        f"{URL}/rest/v1/{table}?select={column}&limit=0",
        headers=headers,
        timeout=10,
    )
    return r.status_code < 400


def check_reference_exists(reference_id: str) -> bool:
    """Check if a legal_reference row exists."""
    headers = {**H}
    r = httpx.get(
        f"{URL}/rest/v1/legal_reference?select=reference_id&reference_id=eq.{reference_id}&limit=1",
        headers=headers,
        timeout=10,
    )
    return r.status_code < 400 and len(r.json()) > 0


def main():
    run_id = start_run("update_findings", "full")
    total_patched = 0
    total_links = 0
    notes_parts = []

    # Check if definition column exists
    has_definition = check_column_exists("finding_type", "definition")
    if not has_definition:
        msg = "definition column missing — apply 0012_finding_content.sql first. Skipping definitions."
        log.warning(msg)
        notes_parts.append(msg)

    # ── 1. Update finding_type titles + definitions ──
    for code, data in FINDING_TYPES.items():
        payload = {"title": data["title"]}
        if has_definition:
            payload["definition"] = data["definition"]
        if patch_row("finding_type", "code", code, payload):
            total_patched += 1
            log.info("finding_type %s → title updated", code)
        else:
            log.error("finding_type %s → PATCH failed", code)

    # ── 2. Update recommendation_library body_templates ──
    for code, data in RECOMMENDATIONS.items():
        payload = {
            "title": data["title"],
            "body_template": data["body_template"],
            "source_note": data["source_note"],
        }
        if patch_row("recommendation_library", "finding_type_code", code, payload):
            total_patched += 1
            log.info("recommendation %s → body_template updated", code)
        else:
            log.error("recommendation %s → PATCH failed", code)

    # ── 3. Insert finding_legal_reference links ──
    # First verify which reference_ids exist
    valid_rows = []
    skipped_refs = []
    for code, ref_id, is_primary, rationale in FINDING_LEGAL_REFS:
        if check_reference_exists(ref_id):
            valid_rows.append({
                "finding_type_code": code,
                "reference_id": ref_id,
                "is_primary": is_primary,
                "rationale": rationale,
            })
        else:
            skipped_refs.append(ref_id)
            log.warning("Skipping link %s → %s: reference_id not found", code, ref_id)

    if skipped_refs:
        notes_parts.append(f"skipped refs: {skipped_refs}")

    if valid_rows:
        n = upsert("finding_legal_reference", valid_rows, "finding_type_code,reference_id")
        total_links = n
        log.info("finding_legal_reference: upserted %d rows", n)

    # Finish
    status = "ok" if not notes_parts else "partial"
    finish_run(
        run_id,
        inserted=total_links,
        updated=total_patched,
        status=status,
        notes="; ".join(notes_parts) if notes_parts else "",
    )

    print(f"\n{'='*60}")
    print(f"  Finding types patched: {total_patched} (of {len(FINDING_TYPES) + len(RECOMMENDATIONS)})")
    print(f"  Legal reference links: {total_links}")
    if skipped_refs:
        print(f"  Skipped (ref not found): {skipped_refs}")
    if not has_definition:
        print("  NOTE: definition column missing — run 0012_finding_content.sql")
    print(f"  Ingestion run: {run_id}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
