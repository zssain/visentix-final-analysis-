#!/usr/bin/env python3
"""Generate WeasyPrint-safe report colours from the light theme tokens.

``web/src/theme.css`` remains the single colour authority. The report layout is
kept in ``report.template.css`` because WeasyPrint cannot consume OKLCH; this
script converts the light-mode tokens to clamped sRGB and emits both the runtime
stylesheet and the small Python constant map needed by inline SVG markup.

The existing 25/50/75 report ramp cut-points are intentionally not represented
here and are not changed (OD-17 remains expert-owned).
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "web" / "src" / "theme.css"
TEMPLATE = ROOT / "app" / "services" / "report" / "report.template.css"
OUTPUT_CSS = ROOT / "app" / "services" / "report" / "report.css"
OUTPUT_PY = ROOT / "app" / "services" / "report" / "report_tokens.py"

_OKLCH = re.compile(
    r"oklch\(\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)"
    r"(?:\s*/\s*([0-9.]+)%?)?\s*\)"
)
_DECL = re.compile(r"--([a-z0-9-]+)\s*:\s*(oklch\([^;]+\))\s*;")
_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


def _linear_to_srgb(value: float) -> float:
    return 12.92 * value if value <= 0.0031308 else 1.055 * (value ** (1 / 2.4)) - 0.055


def oklch_to_rgb(value: str) -> tuple[tuple[int, int, int], float, bool]:
    """Convert one CSS OKLCH value to 8-bit sRGB, returning clamp metadata."""
    match = _OKLCH.fullmatch(value.strip())
    if not match:
        raise ValueError(f"unsupported OKLCH value: {value}")
    lightness, chroma, hue = map(float, match.group(1, 2, 3))
    alpha_raw = match.group(4)
    alpha = 1.0
    if alpha_raw is not None:
        parsed = float(alpha_raw)
        alpha = parsed / 100.0 if "%" in value else parsed

    angle = math.radians(hue)
    a = chroma * math.cos(angle)
    b = chroma * math.sin(angle)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    linear = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    encoded = tuple(_linear_to_srgb(channel) for channel in linear)
    clamped = any(channel < 0 or channel > 1 for channel in encoded)
    rgb = tuple(round(max(0.0, min(1.0, channel)) * 255) for channel in encoded)
    return rgb, max(0.0, min(1.0, alpha)), clamped


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def _blend(foreground: tuple[int, int, int], background: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(round(fg * alpha + bg * (1 - alpha)) for fg, bg in zip(foreground, background))


def _theme_tokens() -> tuple[dict[str, tuple[int, int, int]], list[str]]:
    source = THEME.read_text(encoding="utf-8")
    root_match = re.search(r":root\s*\{(.*?)\n\}", source, re.DOTALL)
    if not root_match:
        raise RuntimeError("theme.css has no parseable :root block")
    raw = dict(_DECL.findall(root_match.group(1)))
    required = {
        "background", "foreground", "card", "primary", "primary-foreground",
        "secondary", "muted", "muted-foreground", "border", "ring",
        "standing-good", "standing-mid", "standing-bad",
        "standing-good-fill", "standing-mid-fill", "standing-bad-fill", "brand",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise RuntimeError(f"missing theme tokens: {', '.join(missing)}")

    colors: dict[str, tuple[int, int, int]] = {}
    alphas: dict[str, float] = {}
    clamped_tokens: list[str] = []
    for name in sorted(required):
        rgb, alpha, clamped = oklch_to_rgb(raw[name])
        colors[name] = rgb
        alphas[name] = alpha
        if clamped:
            clamped_tokens.append(name)

    # Print is light-mode only; translucent standing fills are composited over
    # the card token so WeasyPrint receives a plain deterministic hex.
    for name in ("standing-good-fill", "standing-mid-fill", "standing-bad-fill"):
        colors[name] = _blend(colors[name], colors["card"], alphas[name])
    return colors, clamped_tokens


def build_outputs() -> tuple[str, str, list[str]]:
    colors, clamped = _theme_tokens()
    derived = {
        "brand-soft": _blend(colors["brand"], colors["card"], 0.10),
        "brand-pale": _blend(colors["brand"], colors["card"], 0.22),
        "brand-light": _blend(colors["brand"], colors["card"], 0.38),
    }
    values = {**colors, **derived}

    css_names = [
        "background", "foreground", "card", "primary", "primary-foreground",
        "secondary", "muted", "muted-foreground", "border", "ring",
        "standing-good", "standing-mid", "standing-bad",
        "standing-good-fill", "standing-mid-fill", "standing-bad-fill",
        "brand", "brand-soft", "brand-pale", "brand-light",
    ]
    token_lines = []
    for name in css_names:
        source = f"--{name}" if name in colors else "--brand (derived light-mode tint)"
        token_lines.append(f"  --pdf-{name}: {_hex(values[name])}; /* source: theme.css {source} */")

    literal_map = {
        "#12365B": "var(--pdf-primary)",
        "#2FB3A0": "var(--pdf-brand)",
        "#1B2A3D": "var(--pdf-foreground)",
        "#5B6B7F": "var(--pdf-muted-foreground)",
        "#DBE2EA": "var(--pdf-border)",
        "#F4F7FA": "var(--pdf-muted)",
        "#FFFFFF": "var(--pdf-card)",
        "#2E9E6B": "var(--pdf-standing-good)",
        "#E9A23B": "var(--pdf-standing-mid)",
        "#D9534F": "var(--pdf-standing-bad)",
        "#C0392B": "var(--pdf-standing-bad)",
        "#E4F3EC": "var(--pdf-standing-good-fill)",
        "#FBEFD9": "var(--pdf-standing-mid-fill)",
        "#B77A18": "var(--pdf-standing-mid)",
        "#FBE4E3": "var(--pdf-standing-bad-fill)",
        "#F7DCDA": "var(--pdf-standing-bad-fill)",
        "#ECF0F4": "var(--pdf-secondary)",
        "#EDF1F5": "var(--pdf-secondary)",
        "#AEBBC9": "var(--pdf-ring)",
        "#DCEDE4": "var(--pdf-standing-good-fill)",
        "#2E5E48": "var(--pdf-standing-good)",
        "#EEF2F6": "var(--pdf-secondary)",
        "#E2E8EF": "var(--pdf-border)",
        "#EAF7F4": "var(--pdf-brand-soft)",
        "#1E7A6C": "var(--pdf-brand)",
        "#FCF3E2": "var(--pdf-standing-mid-fill)",
        "#FBE9E8": "var(--pdf-standing-bad-fill)",
        "#F5FBFA": "var(--pdf-brand-soft)",
        "#9EC7DE": "var(--pdf-brand-light)",
        "#CDE0EC": "var(--pdf-brand-pale)",
    }
    layout = TEMPLATE.read_text(encoding="utf-8")
    for literal, replacement in literal_map.items():
        layout = re.sub(re.escape(literal), replacement, layout, flags=re.IGNORECASE)
    leftovers = sorted(set(_HEX.findall(layout)))
    if leftovers:
        raise RuntimeError(f"unmapped report template colours: {', '.join(leftovers)}")

    old_root = re.search(r":root\s*\{.*?\n\}", layout, re.DOTALL)
    if not old_root:
        raise RuntimeError("report template has no parseable :root block")
    root = ":root {\n" + "\n".join(token_lines) + "\n\n" + "\n".join([
        "  --navy: var(--pdf-primary);",
        "  --teal: var(--pdf-brand);",
        "  --ink: var(--pdf-foreground);",
        "  --muted: var(--pdf-muted-foreground);",
        "  --hair: var(--pdf-border);",
        "  --panel: var(--pdf-muted);",
        "  --white: var(--pdf-card);",
        "  --risk-low: var(--pdf-standing-good);",
        "  --risk-moderate: var(--pdf-standing-mid);",
        "  --risk-high: var(--pdf-standing-bad);",
        "  --risk-elevated: var(--pdf-standing-bad);",
    ]) + "\n}"
    layout = layout[:old_root.start()] + root + layout[old_root.end():]
    header = (
        "/* GENERATED by scripts/build_report_css.py from web/src/theme.css and "
        "report.template.css — DO NOT EDIT.\n"
        " * OD-17: palette is synchronized; the existing 25/50/75 ramp cut-points "
        "remain unchanged. */\n"
    )
    css_output = header + layout

    python_keys = {
        "primary": "primary",
        "primary_foreground": "primary-foreground",
        "muted_foreground": "muted-foreground",
        "border": "border",
        "ring": "ring",
        "brand": "brand",
        "standing_good": "standing-good",
        "standing_mid": "standing-mid",
        "standing_bad": "standing-bad",
    }
    py_lines = [
        '"""GENERATED by scripts/build_report_css.py; do not edit."""',
        "",
        "REPORT_COLORS = {",
    ]
    for key, token in python_keys.items():
        py_lines.append(f'    "{key}": "{_hex(values[token])}",  # theme.css --{token}')
    py_lines.extend(["}", ""])
    return css_output, "\n".join(py_lines), clamped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    css, py, clamped = build_outputs()
    stale = []
    for path, expected in ((OUTPUT_CSS, css), (OUTPUT_PY, py)):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != expected:
            stale.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.write_text(expected, encoding="utf-8")
    if clamped:
        print("Clamped out-of-gamut tokens: " + ", ".join(clamped), file=sys.stderr)
    if args.check and stale:
        print("Generated report assets are stale: " + ", ".join(stale), file=sys.stderr)
        return 1
    print("Report CSS/tokens are up to date." if not stale else "Generated report CSS/tokens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
