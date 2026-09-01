#!/usr/bin/env python3
"""
Masked-surface guard — a preview surface must be ABSENT from an un-flagged build.

release.sh step 5 already greps the release bundle. This runs the same check on
an ordinary build, so the leak is caught at development time rather than at
release time — and it keeps the two identifier lists honest by reading
release.sh's own list instead of duplicating it.

It exists because a leak actually happened: the route registry declared every
route's path and title as plain array members, which bundled masked identifiers
unconditionally. Rollup could not remove them because nothing was conditional.
Separately, release.sh's list had gone stale after the screens were renamed, so
it was grepping for identifiers the code no longer used — the gate would have
passed while the real ones leaked.

Run: python scripts/check_masking.py   (builds with flags off, then greps)
"""
from __future__ import annotations
import ast, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def identifiers() -> dict[str, list[str]]:
    """Read the IDENT map out of release.sh so there is ONE list, not two."""
    src = (ROOT / "scripts" / "release.sh").read_text(encoding="utf-8")
    m = re.search(r"IDENT = \{(.*?)\n\}", src, re.S)
    if not m:
        raise SystemExit("FAIL  could not find IDENT in scripts/release.sh")
    return ast.literal_eval("{" + m.group(1) + "}")


def main() -> int:
    ident = identifiers()
    env = {**os.environ, "VITE_PREVIEW_SURFACES": "false"}
    for k in list(env):
        if k.startswith("VITE_SURFACE_"):
            env.pop(k)
    # .env.local would re-enable preview; --mode production skips .env.local.
    r = subprocess.run(["npm", "run", "build", "--", "--mode", "production"],
                       cwd=WEB, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL  build failed:\n" + r.stderr[-2000:], file=sys.stderr)
        return 1

    bundles = list((WEB / "dist" / "assets").glob("index-*.js"))
    if not bundles:
        print("FAIL  no bundle produced", file=sys.stderr)
        return 1
    js = bundles[0].read_text(encoding="utf-8", errors="ignore")

    leaked = [(surf, tok) for surf, toks in ident.items() for tok in toks if tok in js]
    if leaked:
        print("Masked-surface guard FAILED — identifiers present in an un-flagged build:\n", file=sys.stderr)
        for surf, tok in leaked:
            print(f"  - {surf}: {tok!r}", file=sys.stderr)
        print("\nGate the declaration behind a raw import.meta.env check so Rollup can fold it.", file=sys.stderr)
        return 1

    print(f"Masked-surface guard passed — {sum(len(v) for v in ident.values())} identifiers absent from an un-flagged build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
