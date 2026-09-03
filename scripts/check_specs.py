#!/usr/bin/env python3
"""Fail when mock ownership moved but the retired feature lacks a banner."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKER = ROOT / "visentix-specs" / "00-plan" / "mock-tracker.md"
FEATURES = ROOT / "visentix-specs" / "02-features"
TRANSFER = re.compile(r"\b(F\d{2})→F\d{2}\b")


def transferred_sources() -> set[str]:
    sources: set[str] = set()
    for line in TRACKER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| M-"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        sources.update(match.group(1) for match in TRANSFER.finditer(cells[2]))
    return sources


def main() -> int:
    failures: list[str] = []
    sources = transferred_sources()
    if not sources:
        print("Spec-drift guard FAILED: no ownership transfers parsed", file=sys.stderr)
        return 1

    for feature_id in sorted(sources):
        matches = sorted(FEATURES.glob(f"{feature_id}-*.md"))
        if len(matches) != 1:
            failures.append(
                f"{feature_id}: expected one feature spec, found {len(matches)}"
            )
            continue
        text = matches[0].read_text(encoding="utf-8")
        if not re.search(r"^> \*\*Superseded by .+\*\*$", text, re.MULTILINE):
            failures.append(
                f"{matches[0].relative_to(ROOT)}: mock ownership moved but "
                "the spec has no supersession banner"
            )

    if failures:
        print("Spec-drift guard FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"Spec-drift guard passed — {len(sources)} retired spec(s) are explicit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
