#!/usr/bin/env python3
"""
House-acronym guard (design-system §2 acronym rule; Hard Rule 9 register).

A vendor-coined acronym the reader must memorise is jargon. The SEC Plain
English Handbook puts it almost verbatim: "don't create new jargon that's unique
to your document in the form of acronyms or other words." Established public
terms (GDPR, CCPA, PDF, API) are fine; ours are not.

This scans only what a reader can SEE: JSX text nodes and quoted UI strings.
Comments, identifiers, type names, test files and data keys are exempt -- the
rule is about register, not about internal naming.

Run: python scripts/check_acronyms.py   (exit 1 on any violation)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"

# Acronym -> what to say instead.
BANNED = {
    "VCI":  'say "Confidence"',
    "PGMS": 'say "Privacy programme maturity"',
    "DDR":  "internal design-decision id — never shown to a reader",
    "DIR":  "internal id — never shown to a reader",
    "OD":   "internal open-decision id — never shown to a reader",
}
# Surfaces where a house id is legitimately shown to an internal reader.
EXEMPT_FILES = {
    "components/MockBadge.tsx",       # names its tracker row on purpose
}
EXEMPT_DIRS = ("components/ui/", "test/", "__tests__/")

# JSX text between tags, and double/single-quoted strings.
JSX_TEXT = re.compile(r">([^<>{}]{2,})<")
QUOTED   = re.compile(r'"([^"\\]{2,}?)"' + r"|'([^'\\]{2,}?)'")

def visible_strings(src: str):
    # Strip comments first so a rationale comment never trips the guard.
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"^\s*//.*$", "", src, flags=re.M)
    for m in JSX_TEXT.finditer(src):
        yield m.group(1)
    for m in QUOTED.finditer(src):
        yield m.group(1) or m.group(2) or ""

def main() -> int:
    failures: list[str] = []
    for f in sorted(WEB.rglob("*.tsx")):
        rel = str(f.relative_to(WEB))
        if rel in EXEMPT_FILES or any(d in rel for d in EXEMPT_DIRS):
            continue
        src = f.read_text(encoding="utf-8")
        for text in visible_strings(src):
            for acro, fix in BANNED.items():
                # Whole word, and not part of an identifier like VCI_TITLE.
                if re.search(rf"(?<![A-Za-z0-9_])({acro})(?![A-Za-z0-9_-])", text):
                    failures.append(f"web/src/{rel}: customer-visible \"{acro}\" in {text.strip()[:70]!r} — {fix}")

    if failures:
        print("House-acronym guard FAILED:\n", file=sys.stderr)
        for x in dict.fromkeys(failures):
            print(f"  - {x}", file=sys.stderr)
        return 1
    print("House-acronym guard passed — no house acronyms in reader-visible copy.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
