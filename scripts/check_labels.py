#!/usr/bin/env python3
"""
Naming-contract guard (Workstream 2).

`value.replace(/_/g, " ")` was written inline at 20 call sites. Each was free to
drift, and several enums reached the screen completely raw — a finding's
severity rendered as "high", not "High exposure". A reader saw the database's
vocabulary, worded differently on different screens.

One registry now owns reader-facing labels: web/src/lib/labels.ts. This guard
stops the transformation being reimplemented beside it.

It checks the mechanism, not the wording: an inline underscore-strip in a
component means some label is being invented at a call site again.

Run: python scripts/check_labels.py   (exit 1 on any inline formatting)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"
REGISTRY = "lib/labels.ts"
EXEMPT = {REGISTRY, "lib/domainLabels.ts"}

INLINE = re.compile(r'\.replace\(\s*/[_\-]\+?/g?\s*,')


def main() -> int:
    failures: list[str] = []
    for f in sorted(list(WEB.rglob("*.tsx")) + list(WEB.rglob("*.ts"))):
        rel = f.relative_to(WEB).as_posix()
        if rel in EXEMPT or rel.startswith("test/") or ".test." in f.name:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith(("*", "//", "/*")):
                continue
            if INLINE.search(line):
                failures.append(
                    f"web/src/{rel}:{i}: enum formatted inline — route it through {REGISTRY} "
                    f"(humanize / severityLabel / statusLabel / domainLabel / …)"
                )

    if failures:
        print(f"Naming-contract guard FAILED ({len(failures)}):\n", file=sys.stderr)
        for x in failures:
            print(f"  - {x}", file=sys.stderr)
        return 1
    print("Naming-contract guard passed — reader-facing labels come from one registry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
