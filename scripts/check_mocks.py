#!/usr/bin/env python3
"""
Mock-badge guard.

Two invariants, both about the same failure: a reader cannot tell an invented
number from a measured one.

  1. Any page module that imports a `mockData` module MUST render <MockBadge/>.
  2. Every id passed to <MockBadge id="M-xx"/> MUST exist in the mock tracker,
     and its tracker row must not already be marked Replaced.

Run: python scripts/check_mocks.py   (exit 1 on any violation)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"
TRACKER = ROOT / "visentix-specs" / "00-plan" / "mock-tracker.md"

def tracker_rows() -> dict[str, str]:
    """id -> status column, from the tracker table."""
    rows: dict[str, str] = {}
    for line in TRACKER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| M-"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # | ID | Feature | Screen | What's mocked | Real source | Status | Removal |
        if len(cells) >= 7:
            rows[cells[1]] = cells[6]
    return rows

def main() -> int:
    if not TRACKER.exists():
        print(f"FAIL  mock tracker not found at {TRACKER}", file=sys.stderr)
        return 1
    rows = tracker_rows()
    if not rows:
        print("FAIL  mock tracker parsed zero rows — has the table format changed?", file=sys.stderr)
        return 1

    failures: list[str] = []

    for tsx in sorted(WEB.rglob("*.tsx")):
        if "components/ui" in str(tsx) or "/test" in str(tsx):
            continue
        src = tsx.read_text(encoding="utf-8")
        rel = tsx.relative_to(ROOT)

        imports_mock = re.search(r'from\s+["\'][^"\']*mockData["\']', src) is not None
        has_badge = "<MockBadge" in src

        if imports_mock and not has_badge:
            failures.append(
                f"{rel}: imports mockData but renders no <MockBadge/>. "
                f"An unlabelled illustrative figure is indistinguishable from a fabricated one (Hard Rule 7)."
            )

        for mid in re.findall(r'<MockBadge[^>]*\bid=["\'](M-\d+)["\']', src):
            if mid not in rows:
                failures.append(f"{rel}: <MockBadge id=\"{mid}\"/> is not a row in the mock tracker.")
            elif rows[mid].lower().startswith("**replaced") or rows[mid].lower().startswith("replaced"):
                failures.append(
                    f"{rel}: <MockBadge id=\"{mid}\"/> but the tracker marks {mid} Replaced. "
                    f"Either the badge is stale or the tracker is wrong — they must agree."
                )

    if failures:
        print("Mock-badge guard FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    badged = sum(1 for p in WEB.rglob("*.tsx") if "<MockBadge" in p.read_text(encoding="utf-8"))
    print(f"Mock-badge guard passed — {badged} surface(s) badged, {len(rows)} tracker rows.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
