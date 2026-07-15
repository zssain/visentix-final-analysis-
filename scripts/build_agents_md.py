#!/usr/bin/env python3
"""
build_agents_md.py — compile the GENERATED sections of AGENTS.md
from the foundation specs, so agent instructions can never drift.

Usage:
    python scripts/build_agents_md.py            # rewrite AGENTS.md in place
    python scripts/build_agents_md.py --check    # exit 1 if AGENTS.md is stale (CI mode)

Sections handled (matched by marker name):
    HARD RULES        — from data/hard_rules.md fragment kept next to this script,
                        reviewed by the expert like any spec file
    CURRENT VERSIONS  — parsed from the Version headers + changelogs of
                        visentix-specs/01-foundation/*.md and scoreBands constants
    SPEC INDEX        — built from the titles + Status lines of
                        visentix-specs/02-features/F*.md

Everything outside BEGIN/END GENERATED markers is left byte-identical.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
FOUNDATION = ROOT / "visentix-specs" / "01-foundation"
FEATURES = ROOT / "visentix-specs" / "02-features"
HARD_RULES_SRC = Path(__file__).resolve().parent / "data" / "hard_rules.md"

MARKER = re.compile(
    r"(<!-- BEGIN GENERATED: (?P<name>[A-Z ]+?) \(source: [^)]*\) -->)(?P<body>.*?)(<!-- END GENERATED: (?P=name) -->)",
    re.DOTALL,
)


def version_line(spec: Path) -> str:
    text = spec.read_text(encoding="utf-8")
    m = re.search(r"\*\*Version:\*\*\s*([^\n·]+)(?:·\s*([0-9-]+))?", text)
    version = m.group(1).strip() if m else "unknown"
    date = (m.group(2) or "").strip() if m else ""
    return f"- {spec.name}: v{version}" + (f" ({date})" if date else "")


def build_current_versions() -> str:
    lines = ["## Current versions"]
    for name in ("schema.md", "business-logic.md", "intelligence-logic.md", "design-system.md"):
        p = FOUNDATION / name
        if p.exists():
            lines.append(version_line(p))
    lines.append("- Formula registry: F-001–F-014 (see intelligence-logic.md §7)")
    # Pull live UI constants if the frontend file exists, else keep spec defaults.
    bands = ROOT / "web" / "src" / "lib" / "scoreBands.ts"
    if bands.exists():
        src = bands.read_text(encoding="utf-8")
        n = re.search(r"LOW_CONFIDENCE_COHORT_N\s*=\s*(\d+)", src)
        lines.append("- Score bands: see web/src/lib/scoreBands.ts (single source of truth)")
        if n:
            lines.append(f"- LOW_CONFIDENCE_COHORT_N: {n.group(1)}")
    else:
        lines.append("- Score bands: ≥70 red / ≥45 gold / else teal (`web/src/lib/scoreBands.ts`)")
        lines.append("- LOW_CONFIDENCE_COHORT_N: 10 (OD-05 pending)")
    return "\n".join(lines)


def build_spec_index() -> str:
    lines = ["## Feature spec index"]
    for spec in sorted(FEATURES.glob("F*.md")):
        text = spec.read_text(encoding="utf-8")
        title_m = re.search(r"^#\s+(F\d+\s+—\s+.+)$", text, re.MULTILINE)
        status_m = re.search(r"\*\*Status:\*\*\s*([^·\n]+)", text)
        title = title_m.group(1).strip() if title_m else spec.stem
        status = status_m.group(1).strip() if status_m else "unknown"
        lines.append(f"- {title} — {status}")
    return "\n".join(lines)


def build_hard_rules() -> str:
    if HARD_RULES_SRC.exists():
        return HARD_RULES_SRC.read_text(encoding="utf-8").strip()
    # Fall back to whatever is currently in AGENTS.md (first run bootstrap).
    return None  # signals "leave as-is"


BUILDERS = {
    "HARD RULES": build_hard_rules,
    "CURRENT VERSIONS": build_current_versions,
    "SPEC INDEX": build_spec_index,
}


def regenerate(text: str) -> str:
    def repl(m: re.Match) -> str:
        builder = BUILDERS.get(m.group("name").strip())
        body = builder() if builder else None
        if body is None:
            return m.group(0)  # no source available; keep existing content
        return f"{m.group(1)}\n{body}\n{m.group(4)}"

    return MARKER.sub(repl, text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if AGENTS.md is stale")
    args = ap.parse_args()

    original = AGENTS.read_text(encoding="utf-8")
    updated = regenerate(original)

    if args.check:
        if original != updated:
            print("AGENTS.md is stale relative to the specs.")
            print("Run: python scripts/build_agents_md.py  (and commit the result)")
            return 1
        print("AGENTS.md is up to date.")
        return 0

    if original != updated:
        AGENTS.write_text(updated, encoding="utf-8")
        print("AGENTS.md regenerated.")
    else:
        print("AGENTS.md already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
