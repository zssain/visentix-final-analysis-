#!/usr/bin/env python3
"""
Literal-colour guard (L-016).

`theme.css` is the only place a colour value may be defined. That was true of
the tokens and false of the product: `.badge-*` held a literal hex per class, so
the traffic-light decision (OD-13) changed the tokens and left 73 call sites
untouched — `.badge-moderate` was green while labelling middling things, and
`.badge-moderate` and `.badge-low` were the SAME colour, rendering two different
standings indistinguishably.

A token layer only governs what reads from it. This closes the gap: a literal
colour anywhere but the token layer fails the build.

Exempt, deliberately:
  - web/src/theme.css                the token layer itself
  - true blacks/whites in scrims, shadows and overlays (rgb(0 0 0 / …)), which
    are not theme colours and must not flip with the theme
  - the PDF stylesheet, which cannot read oklch and is tracked by OD-17
  - vendored shadcn primitives, which ship their own neutral defaults

Run: python scripts/check_colors.py   (exit 1 on any literal)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"

EXEMPT_FILES = {"theme.css"}
EXEMPT_DIRS = ("components/ui/",)
# The print stylesheet is a separate, tracked problem (OD-17): WeasyPrint cannot
# parse oklch(), so the PDF keeps hex until its values are GENERATED from
# theme.css. Listing it here keeps the guard honest rather than silently broad.
EXEMPT_PATHS = {"report/report.css"}

HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
RGBA = re.compile(r"\brgba?\(\s*\d+[\s,]")
NAMED = re.compile(r"(?<![\w-])(?:background|color|border-color|fill|stroke)\s*:\s*(?:red|green|blue|orange|purple|teal|gold|navy|white|black)\b")


def is_true_black_or_white(line: str) -> bool:
    """rgb(0 0 0 / x) and rgba(255,255,255,x) in a shadow/scrim are not theme
    colours — a drop shadow does not invert with the palette."""
    return bool(re.search(r"rgba?\(\s*(?:0[\s,]+0[\s,]+0|255[\s,]+255[\s,]+255)", line))


def main() -> int:
    failures: list[str] = []
    for f in sorted(list(WEB.rglob("*.css")) + list(WEB.rglob("*.tsx")) + list(WEB.rglob("*.ts"))):
        rel = f.relative_to(WEB).as_posix()
        if f.name in EXEMPT_FILES or rel in EXEMPT_PATHS: continue
        # Tests legitimately name retired colours to assert they are gone.
        if any(d in rel for d in EXEMPT_DIRS): continue
        if rel.startswith("test/") or ".test." in f.name: continue

        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            # Comments explain the values; they are not the values.
            if stripped.startswith(("*", "//", "/*", "#")): continue
            if is_true_black_or_white(line): continue
            # NAMED only applies to stylesheets. In TSX `color: teal ? a : b`
            # is a ternary on a variable called `teal`, not the CSS colour —
            # matching it there produced a false positive on real code.
            hit = HEX.search(line) or RGBA.search(line) or (
                NAMED.search(line) if f.suffix == ".css" else None)
            if hit:
                failures.append(f"web/src/{rel}:{i}: literal colour {hit.group(0)!r} — use a token from theme.css")

    if failures:
        print(f"Literal-colour guard FAILED ({len(failures)}):\n", file=sys.stderr)
        for x in failures[:40]:
            print(f"  - {x}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  … and {len(failures) - 40} more", file=sys.stderr)
        return 1
    print("Literal-colour guard passed — every colour comes from theme.css.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
