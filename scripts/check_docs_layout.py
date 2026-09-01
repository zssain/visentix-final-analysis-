#!/usr/bin/env python3
"""
Docs-layout guard (Workstream 1 — truth reconciliation).

The repo root accumulated 23 markdown files of four different kinds, and the
distinction that mattered was invisible: a superseded readiness report and a
live open decision looked identical. Two expert-owned decisions sat there for
five weeks outside the OD register.

Four classes, one home each:

  standing truth  rules that govern the build   visentix-specs/, AGENTS.md
  ledger          append-only history           logs/decision-log.md, 04-lessons/, 00-plan/open-decisions.md
  dated record    true on its date only         logs/archive/YYYY-MM/
  runbook         living operational procedure  docs/runbooks/

This guard enforces the cheap, checkable half: the root stays clean, dated
records are filed by month, and no NEW decision memo appears outside the
register.

Run: python scripts/check_docs_layout.py   (exit 1 on any violation)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The only markdown allowed at the repo root.
ROOT_ALLOWLIST = {
    "README.md",   # entry point
    "AGENTS.md",   # generated standing truth (scripts/build_agents_md.py)
}

# A file whose name says "this is a decision" belongs in the OD register, not
# loose in the tree. Archived copies are fine — they are the source record.
DECISION_NAME = re.compile(r"DECISION[-_]NEEDED|[-_]DRAFT\.md$", re.I)

ARCHIVE_MONTH = re.compile(r"^logs/archive/\d{4}-\d{2}/")

def main() -> int:
    failures: list[str] = []

    # 1. Root stays clean.
    for f in sorted(ROOT.glob("*.md")):
        if f.name not in ROOT_ALLOWLIST:
            failures.append(
                f"{f.name}: new root-level markdown. Classify it — "
                f"dated record -> logs/archive/YYYY-MM/, runbook -> docs/runbooks/, "
                f"standing truth -> visentix-specs/, decision -> open-decisions.md."
            )

    # 2. Archived records are filed by month.
    archive = ROOT / "logs" / "archive"
    if archive.exists():
        for f in archive.rglob("*.md"):
            rel = f.relative_to(ROOT).as_posix()
            # The archive's own index is a guide to the records, not a record.
            if rel == "logs/archive/README.md":
                continue
            if not ARCHIVE_MONTH.match(rel):
                failures.append(f"{rel}: archived record is not under logs/archive/YYYY-MM/.")

    # 3. No decision memo outside the register (archived copies exempt).
    tracked = [p for p in ROOT.rglob("*.md")
               if not any(part in {".git", "node_modules", ".venv", "dist"} for part in p.parts)]
    for f in tracked:
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith("logs/archive/"):
            continue
        if DECISION_NAME.search(f.name):
            failures.append(
                f"{rel}: a decision memo outside logs/archive/. Register it in "
                f"visentix-specs/00-plan/open-decisions.md and archive the memo — "
                f"a decision nobody can find in the register is a decision nobody makes."
            )

    if failures:
        print("Docs-layout guard FAILED:\n", file=sys.stderr)
        for x in failures:
            print(f"  - {x}", file=sys.stderr)
        return 1

    n_arch = len(list((ROOT / "logs" / "archive").rglob("*.md"))) if archive.exists() else 0
    n_run = len(list((ROOT / "docs" / "runbooks").glob("*.md")))
    print(f"Docs-layout guard passed — root clean, {n_arch} archived record(s), {n_run} runbook(s).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
