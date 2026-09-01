#!/usr/bin/env python3
"""
Dead-CSS guard — a stylesheet must not outlive the markup it styled.

intake.css carried 24 classes for a results pane that had been deleted weeks
earlier: 183 of its 413 lines styled markup that no longer existed. Dead CSS is
not merely waste — it makes a stylesheet look bigger than the work of retiring
it actually is, and it hides which rules still matter.

Each page stylesheet is checked against the .tsx files beside it. A class
defined but referenced nowhere fails.

Exempt: theme.css (tokens, not classes) and index.css (the legacy bridge, which
is retired wholesale rather than class by class).

Run: python scripts/check_dead_css.py   (exit 1 on any dead class)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"
EXEMPT = {"theme.css", "index.css"}

CLASS_DEF = re.compile(r"^\s*\.([a-zA-Z][\w-]*)", re.M)


def main() -> int:
    failures: list[str] = []
    for css in sorted(WEB.rglob("*.css")):
        if css.name in EXEMPT:
            continue
        classes = set(CLASS_DEF.findall(css.read_text(encoding="utf-8")))
        if not classes:
            continue
        # Markup that could reference it: the directory's own tsx, plus report
        # sections which share report.css from a subdirectory.
        scope = list(css.parent.rglob("*.tsx"))
        if not scope:
            scope = list(WEB.rglob("*.tsx"))
        markup = "\n".join(f.read_text(encoding="utf-8") for f in scope)

        dead = sorted(c for c in classes
                      if not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", markup))
        for c in dead:
            failures.append(f"{css.relative_to(ROOT.parent) if False else css.relative_to(WEB)}: .{c} is defined but never used")

    if failures:
        print(f"Dead-CSS guard FAILED ({len(failures)}):\n", file=sys.stderr)
        for x in failures[:40]:
            print(f"  - {x}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  … and {len(failures) - 40} more", file=sys.stderr)
        return 1
    print("Dead-CSS guard passed — every class in a page stylesheet is referenced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
