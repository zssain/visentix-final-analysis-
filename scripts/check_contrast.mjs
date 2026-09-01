#!/usr/bin/env node
/**
 * Palette guard — WCAG AA contrast of the standing scale.
 *
 * The standing colours (traffic light, OD-13) are the only colours that carry
 * judgement about a score, and they are read AS TEXT. A washed-out number is a
 * legibility bug, not a style choice: #A87400 shipped at 4.07:1 and failed AA.
 *
 * This computes contrast from web/src/theme.css rather than trusting the
 * comments in it, so the comments can never drift from the values.
 *
 * Usage: node scripts/check_contrast.mjs      (exit 1 on any failure)
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const AA = 4.5;
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const css = readFileSync(join(root, "web/src/theme.css"), "utf8");

const srgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
const lin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
const clamp = (x) => Math.max(0, Math.min(1, x));

function oklchToRgb(L, C, H) {
  const A = C * Math.cos((H * Math.PI) / 180), B = C * Math.sin((H * Math.PI) / 180);
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ].map((v) => srgb(clamp(v)));
}
const luminance = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
function contrast(a, b) {
  const l1 = luminance(a), l2 = luminance(b);
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** Read a token from a specific block (`:root` or `.dark`). */
function token(block, name) {
  const b = css.match(new RegExp(`${block.replace(".", "\\.")}\\s*\\{([\\s\\S]*?)\\n\\}`));
  if (!b) throw new Error(`block ${block} not found in theme.css`);
  const m = b[1].match(new RegExp(`--${name}:\\s*oklch\\(([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)`));
  if (!m) throw new Error(`--${name} not found (or not oklch) in ${block}`);
  return oklchToRgb(+m[1], +m[2], +m[3]);
}

// Secondary text has to clear AA on EVERY surface it can land on, not just the
// card. `--muted-foreground` was shipping at 4.45:1 on the sidebar — below AA,
// and unnoticed because this guard only ever looked at the standing scale on a
// card. Most of the words on a screen are muted-foreground; it is the last token
// that should go unchecked.
const CASES = [
  [":root", "card",       ["standing-good", "standing-mid", "standing-bad", "muted-foreground"]],
  [":root", "background", ["muted-foreground", "foreground"]],
  [":root", "sidebar",    ["muted-foreground", "sidebar-foreground"]],
  [":root", "muted",      ["muted-foreground"]],
  [".dark", "card",       ["standing-good", "standing-mid", "standing-bad", "muted-foreground"]],
  [".dark", "background", ["muted-foreground", "foreground"]],
  [".dark", "sidebar",    ["muted-foreground", "sidebar-foreground"]],
  [".dark", "muted",      ["muted-foreground"]],
];

let failed = 0;
for (const [block, bgName, fgNames] of CASES) {
  const bg = token(block, bgName);
  for (const fg of fgNames) {
    const ratio = contrast(token(block, fg), bg);
    const ok = ratio >= AA;
    if (!ok) failed++;
    console.log(`${ok ? "PASS" : "FAIL"}  ${block.padEnd(6)} --${fg.padEnd(18)} on --${bgName.padEnd(10)} ${ratio.toFixed(2)}:1  (need ${AA})`);
  }
}
if (failed) {
  console.error(`\n${failed} colour pair(s) below WCAG AA ${AA}:1 as text. Fix theme.css.`);
  process.exit(1);
}
console.log(`\nAll ${CASES.reduce((n, [, , f]) => n + f.length, 0)} text/surface pairs clear WCAG AA.`);
