#!/usr/bin/env python3
"""Render a Markdown review into a Visentix-branded executive PDF.

Reusable for any report: a designed cover page (title + meta), running
header/footer with page numbers, color-coded severity badges, and styled
tables/callouts. Uses WeasyPrint (already a project dependency).

Usage:
    python scripts/build_review_pdf.py [INPUT.md] [OUTPUT.pdf]

Defaults:
    INPUT  = CODEBASE-REVIEW-2026-08-04.md
    OUTPUT = same name with .pdf

Deps: markdown, weasyprint  (pip install markdown  — weasyprint ships already)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
CSS = Path(__file__).resolve().parent / "review_pdf.css"

SEV = {"Critical", "High", "Medium", "Low", "Informational"}


def split_front_matter(md: str) -> tuple[str, str, str]:
    """Return (title, meta_md, body_md).

    Title = first `# ` heading. Meta = the `**Key:** value` lines in the
    preamble. Body = everything from the first `---` onward, with any preamble
    blockquote (e.g. a scope note) prepended so it opens the body.
    """
    parts = re.split(r"\n---\s*\n", md, maxsplit=1)
    preamble = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    title = "Report"
    meta_lines: list[str] = []
    note_lines: list[str] = []
    for line in preamble.splitlines():
        s = line.strip()
        if s.startswith("# ") and title == "Report":
            title = s[2:].strip()
        elif s.startswith("**"):
            meta_lines.append(s)
        elif s.startswith(">"):
            note_lines.append(line)

    body = ("\n".join(note_lines) + "\n\n" + rest) if note_lines else rest
    return title, "\n".join(meta_lines), body


def badge_severities(html: str) -> str:
    """Wrap severity keywords in colored badges (table cells) / inline spans."""
    # Table cells that are exactly a severity word.
    def cell(m: re.Match) -> str:
        word = m.group(2)
        return f'{m.group(1)}<span class="sev sev-{word.lower()}">{word}</span>{m.group(3)}'

    html = re.sub(
        rf'(<td[^>]*>)\s*({"|".join(SEV)})\s*(</td>)', cell, html
    )
    # Inline "Severity:</strong> High ·" in finding bodies.
    html = re.sub(
        rf'(Severity:\s*</strong>\s*)({"|".join(SEV)})',
        lambda m: f'{m.group(1)}<span class="sev-inline sev-{m.group(2).lower()}">{m.group(2)}</span>',
        html,
    )
    return html


def build(input_md: Path, output_pdf: Path) -> None:
    raw = input_md.read_text(encoding="utf-8")
    title, meta_md, body_md = split_front_matter(raw)

    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    meta_html = md.convert(meta_md)
    md.reset()
    body_html = badge_severities(md.convert(body_md))

    # Split the title on an em/en dash so "Visentix — X" → brand line + report title.
    sub = "Security · Data Integrity · AI/ML · Production Readiness"
    m = re.match(r"(.*?)\s+[—–]\s+(.*)", title)
    cover_title = m.group(2) if m else title

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{CSS.as_uri()}"></head><body>
<section class="cover">
  <div class="cover-brand">VISENTIX</div>
  <div class="cover-tagline">Privacy Intelligence · Benchmarking · Visibility</div>
  <h1 class="cover-title">{cover_title}</h1>
  <div class="cover-sub">{sub}</div>
  <div class="cover-rule"></div>
  <div class="cover-meta">{meta_html}</div>
  <div class="cover-confidential">CONFIDENTIAL — VISENTIX INTERNAL USE ONLY</div>
</section>
<main>{body_html}</main>
</body></html>"""

    HTML(string=doc, base_url=str(ROOT)).write_pdf(str(output_pdf))
    print(f"✓ {output_pdf.relative_to(ROOT)}  ({output_pdf.stat().st_size // 1024} KB)")


def main() -> None:
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "CODEBASE-REVIEW-2026-08-04.md"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else inp.with_suffix(".pdf")
    if not inp.exists():
        sys.exit(f"Input not found: {inp}")
    build(inp, out)


if __name__ == "__main__":
    main()
