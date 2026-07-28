"""Golden notices (F17 component 4) — freeze + CI diff.

Freezes the DETERMINISTIC full-pipeline output (decompose → classify → per-domain
maturity → deterministic F-002…F-010 with fixed scoring inputs) for blessed
notices into tests/golden/notices/<slug>.json. A CI diff test fails on any drift;
only a change to a cited formula_version may legitimately alter a golden file.

The 3 real public retail notices (strong/mid/weak) are OQ-1 — SME blesses or
swaps them. The FIXTURES below are ENGINEER PROPOSALS (retail-cohort, spanning
disclosure strength) with stated rationale; re-freeze after the SME blesses.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.services.intake.decompose import decompose

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden" / "notices"

# Deterministic scoring inputs (fixed) so a golden file is a pure function of
# (notice text + formula_version). Mirrors tests/test_live_pipeline fixtures.
FORMULA_VERSION_SET = {"scoring": "F-002..F-010_v1", "decompose": "decompose-v2-noisefilter"}

# ENGINEER-PROPOSED retail-cohort notices (SME blesses/swaps — OQ-1).
# Rationale: three points on the disclosure-strength axis, retail phrasing.
FIXTURES = {
    "retail_strong": {
        "rationale": "STRONG: names concrete rights, retention period, opt-out, security specifics.",
        "text": """# Privacy Notice

## Information We Collect
We collect your name, email address, shipping address, and order history when you place an order.

## How We Share Data
We share your personal information with shipping carriers and payment processors solely to fulfill your order. We do not sell your personal information.

## Your Rights
You have the right to access, delete, correct, and port your personal data, and to opt out of targeted advertising at any time.

## Data Retention
We retain your order data for 24 months, after which it is deleted.

## Security
We protect your data with AES-256 encryption and multi-factor authentication.
""",
    },
    "retail_mid": {
        "rationale": "MID: some rights + sharing described, vaguer retention, partial specifics.",
        "text": """# Privacy Notice

## Data We Collect
We collect information you provide and data about your use of our store.

## Sharing
We may share data with third-party partners and service providers to operate and improve our services.

## Choices
You may request access to or deletion of your data by contacting us.

## Retention
We keep your data for as long as necessary to provide our services.
""",
    },
    "retail_weak": {
        "rationale": "WEAK: vague, few concrete rights, undefined retention, broad sharing language.",
        "text": """# Privacy Policy

We collect certain information to provide our services. We may share information
with partners and affiliates as appropriate. We use your data to improve your
experience. Contact us with any questions.
""",
    },
}


def _pipeline_output(text: str) -> dict:
    """Deterministic, network-free slice of the pipeline (decompose + classify +
    per-domain maturity). LLM/enforcement excluded so the golden file is stable."""
    n = decompose(text)
    substantive = [c for c in n.clauses if not c.is_noise]
    cats = Counter(c.category for c in substantive)
    domain_maturity = {d: min(cnt * 15, 100) for d, cnt in sorted(cats.items()) if d != "other"}
    return {
        "sections": len(n.sections),
        "clauses_total": len(n.clauses),
        "clauses_substantive": len(substantive),
        "clauses_noise": sum(1 for c in n.clauses if c.is_noise),
        "category_counts": dict(sorted(cats.items())),
        "domain_maturity": domain_maturity,
        "domains_present": sorted(d for d in cats if d != "other"),
        "formula_version_set": FORMULA_VERSION_SET,
    }


def freeze_all() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for slug, spec in FIXTURES.items():
        out = {"slug": slug, "status": "PROPOSED — pending SME bless/swap (OQ-1)",
               "rationale": spec["rationale"], "output": _pipeline_output(spec["text"])}
        (GOLDEN_DIR / f"{slug}.json").write_text(json.dumps(out, indent=2))
        print(f"froze {slug}.json")


def diff(slug: str, text: str) -> list[str]:
    """Return human-readable drift lines for a slug vs its frozen golden file."""
    path = GOLDEN_DIR / f"{slug}.json"
    if not path.exists():
        return [f"no golden file for {slug} (freeze it first)"]
    golden = json.loads(path.read_text())["output"]
    current = _pipeline_output(text)
    drift = []
    for k in golden:
        if golden[k] != current.get(k):
            fv = golden.get("formula_version_set")
            drift.append(f"{slug}.{k}: golden={golden[k]} current={current.get(k)} "
                         f"(legitimate ONLY if a cited formula_version changed: {fv})")
    return drift


if __name__ == "__main__":
    freeze_all()
