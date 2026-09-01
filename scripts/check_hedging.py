#!/usr/bin/env python3
"""
Hedging guard — stacked qualifiers read as evasion, not as care.

ICAEW's Auditor Reporting Lab, on commissioned discourse analysis, names
"pervasive hedging" — piled-up modal verbs and conditional clauses like
"might or might not emerge" or "if it was concluded that a breach had occurred"
— as producing "unnecessarily complex sentences" and "the impression of a high
level of subjectivity."

The rule is NOT "remove uncertainty". The same source is explicit that
"No-one would thank auditors for being definitive where genuine uncertainty
exists," and the trust research says quantified bands preserve trust where vague
hedging erodes it. So: keep the uncertainty, state it once, and state it as a
band rather than as three modal verbs in a row.

This guard therefore flags STACKING, not hedging. One qualifier in a sentence is
fine and expected. Two or more in one sentence is what the analysis names.

Scope: authored, reader-facing copy — the report renderer's static prose and the
recommendation library. Generated LLM prose is guarded separately by the
banned-term filter at draft time.

Run: python scripts/check_hedging.py   (exit 1 on any stacked sentence)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Qualifiers. Deliberately narrow — these are the ones that stack.
HEDGES = [
    "may", "might", "could", "possibly", "potentially", "perhaps",
    "arguably", "generally", "typically", "somewhat", "relatively",
    "appears to", "seems to", "tends to", "in some cases", "it is possible",
]
HEDGE_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(h) for h in HEDGES) + r")(?![\w-])", re.I)

#: Files whose authored copy a reader sees.
TARGETS = [
    ROOT / "app" / "services" / "report" / "renderer.py",
    ROOT / "web" / "src" / "report" / "sections",
    ROOT / "web" / "src" / "report" / "ReportView.tsx",
]

STRING = re.compile(r'"([^"\\]{40,})"|\'([^\'\\]{40,})\'')
MAX_HEDGES_PER_SENTENCE = 1


def sentences(text: str):
    for s in re.split(r"(?<=[.!?])\s+", text):
        if len(s.split()) >= 6:
            yield s


def main() -> int:
    failures: list[str] = []
    files: list[Path] = []
    for t in TARGETS:
        files.extend(sorted(t.rglob("*.py")) + sorted(t.rglob("*.tsx")) if t.is_dir() else [t])

    for f in files:
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")
        # Comments explain the copy; they are not the copy.
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"^\s*(//|#).*$", "", src, flags=re.M)
        for m in STRING.finditer(src):
            text = m.group(1) or m.group(2) or ""
            for s in sentences(text):
                found = HEDGE_RE.findall(s)
                if len(found) > MAX_HEDGES_PER_SENTENCE:
                    failures.append(
                        f"{f.relative_to(ROOT)}: {len(found)} qualifiers in one sentence "
                        f"({', '.join(sorted(set(x.lower() for x in found)))}) — {s.strip()[:90]!r}"
                    )

    if failures:
        print(f"Hedging guard FAILED ({len(failures)}):\n", file=sys.stderr)
        for x in dict.fromkeys(failures):
            print(f"  - {x}", file=sys.stderr)
        print("\nState the uncertainty once, as a band. Keep it — do not delete it.", file=sys.stderr)
        return 1
    print("Hedging guard passed — no sentence stacks qualifiers in reader-facing copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
