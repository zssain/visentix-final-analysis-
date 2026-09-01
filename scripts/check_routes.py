#!/usr/bin/env python3
"""
Route guard — the registry, the spec and the pages must agree.

A route used to be described in four places that could disagree, and did:
the <Route> element, the sidebar link, the page's own PageHeader, and
design-system §6. Measured drift when this was written: `/bulk` was "Bulk
Analysis" in the spec and "Bulk Screening" in code; `/partner` carried two
different nav labels; five routes were absent from the spec map entirely.

Checks:
  1. Every path in web/src/routes/registry.ts appears in design-system §6.
  2. Every path in design-system §6 is declared in the registry.
  3. Nav label and title agree between the two.
  4. Every route the router registers is declared in the registry.
  5. No route declares a nav label without a group, or vice versa.

Run: python scripts/check_routes.py   (exit 1 on any disagreement)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "web" / "src" / "routes" / "registry.ts"
APP = ROOT / "web" / "src" / "App.tsx"
SPEC = ROOT / "visentix-specs" / "01-foundation" / "design-system.md"


def parse_registry() -> dict[str, dict]:
    """Read the ROUTES array. Deliberately a text parse, not a JS eval: the guard
    must not need a node runtime to run in CI."""
    src = REGISTRY.read_text(encoding="utf-8")
    body = src[src.index("export const ROUTES"):src.index("export const ROUTE_REDIRECTS")]
    out: dict[str, dict] = {}
    # Entries are either plain `{ ... }` members or, for maskable surfaces,
    # `...(FLAG ? [{ ... }] : [])` so Rollup can fold them out of a masked
    # build. Both forms declare a route and both must be checked.
    for block in re.split(r"\n  (?:\{|\.\.\.\([A-Z_]+ \? \(\[\{)", body)[1:]:
        path = re.search(r'path:\s*"([^"]+)"', block)
        if not path:
            continue
        out[path.group(1)] = {
            "title": (re.search(r'title:\s*"([^"]+)"', block) or [None, None])[1],
            "navLabel": (m.group(1) if (m := re.search(r'navLabel:\s*"([^"]+)"', block)) else None),
            "group": (m.group(1) if (m := re.search(r'group:\s*"([^"]+)"', block)) else None),
        }
    return out


def parse_spec() -> dict[str, tuple[str, str]]:
    """Read the §6 route-map table: | `/path` | Nav label | Title |."""
    src = SPEC.read_text(encoding="utf-8")
    sec = src[src.index("## 6. Route map"):]
    sec = sec[:sec.index("\n## ")] if "\n## " in sec[3:] else sec
    out: dict[str, tuple[str, str]] = {}
    for line in sec.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", line)
        if m:
            out[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    return out


def parse_router_paths() -> set[str]:
    return set(re.findall(r'<Route\s+path="([^"]+)"', APP.read_text(encoding="utf-8")))


def main() -> int:
    reg, spec, router = parse_registry(), parse_spec(), parse_router_paths()
    if not reg:
        print("FAIL  could not parse routes/registry.ts", file=sys.stderr); return 1
    if not spec:
        print("FAIL  could not parse design-system §6", file=sys.stderr); return 1

    failures: list[str] = []

    for path, d in reg.items():
        if bool(d["navLabel"]) != bool(d["group"]):
            failures.append(f"{path}: navLabel and group must be declared together (one is missing).")

    for path in sorted(set(reg) - set(spec)):
        failures.append(f"{path}: declared in the registry but missing from design-system §6.")
    for path in sorted(set(spec) - set(reg)):
        failures.append(f"{path}: in design-system §6 but not declared in the registry.")

    for path in sorted(set(reg) & set(spec)):
        nav, title = spec[path]
        want_nav = reg[path]["navLabel"] or "—"
        if nav not in ("—", "") and nav != want_nav:
            failures.append(f'{path}: nav label "{nav}" in §6 vs "{want_nav}" in the registry.')
        # §6 titles may carry a trailing footnote marker.
        if title.rstrip(" *") and reg[path]["title"] and title.rstrip(" *") != reg[path]["title"]:
            failures.append(f'{path}: title "{title}" in §6 vs "{reg[path]["title"]}" in the registry.')

    redirects = set(re.findall(r'"(/[^"]*)":\s*"/', REGISTRY.read_text(encoding="utf-8")))
    for path in sorted(router - set(reg) - redirects):
        if path == "*":
            continue
        failures.append(f"{path}: registered by the router but not declared in the registry.")

    if failures:
        print("Route guard FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"Route guard passed — {len(reg)} routes agree across registry, §6 and the router.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
