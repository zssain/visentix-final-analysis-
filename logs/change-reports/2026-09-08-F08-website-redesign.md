# F08 — Website redesign

Rebuilt the eight public website pages with an independent editorial visual
system based on the owner's DOCX references. Ivory, forest green and citron;
large serif headings, a typographic Visentix wordmark, original architectural
SVG artwork, spacious solutions dropdown, and large footer. Scroll reveals
respect reduced motion. No claims of scale, fictional reports, invented scores
or contact receipt states were added.

## Scope and files

- `web/src/pages/public/`: rebuilt all eight page components plus `PublicLayout`
  and `shared`; added `website.css` for isolated responsive styles and motion.
- `web/src/theme.css`: added namespaced public-site palette. Application tokens
  and the user's saved application theme remain unchanged.
- `web/public/visentix-site.svg`: website favicon; layout restores the existing
  app favicon/title when leaving the website.
- `web/src/test/public_site.test.tsx`: scoped the existing workspace navigation
  assertion to the header because the redesigned footer also has the link.
  Its destination and authorization assertions are preserved.
- F08 public-site amendment, README and decision log: recorded the owner's
  design/logo override and new run instructions.
- `logs/audits/2026-09-08-website-redesign/`: local screenshots and responsive
  measurements, with no customer data.

Tables/columns: none. Migrations: none. Dependencies installed: none. App backend,
scoring, persisted reports and authenticated screen designs were not modified.
Website artwork is decorative, not a product screenshot or a data visualization.

## Run

```sh
cd web
pnpm run dev
```

Local preview: http://localhost:5173/. The review server was started with
`pnpm run dev --host 0.0.0.0 --port 5173` so the Windows host can reach WSL.
The preview remains running. Changes are local, not deployed or pushed.

## Validation

- Full frontend suite: 23 files, 228 tests pass.
- `pnpm run build`: passes; existing bundle-size warning remains.
- `make guards`: passed, including application contrast, route/masking and CSS
  checks. Generated AGENTS consistency and diff whitespace checks also pass.
- Chromium: all eight website routes at 375/768/1440px; one h1 each, no horizontal
  page overflow, no uncaught page errors. No live login was performed.
- Desktop dropdown: Enter opens, Escape closes and returns focus to Solutions;
  full-header width without overflow. Mobile link closes the drawer and navigates.
- Scroll reveal becomes visible on entry; reduced motion leaves content visible
  without a translated position.
- Backend unchanged: the earlier isolated run remains 1013 passed, 268 skipped,
  one pre-existing PDF determinism failure (OD-18). The full backend gate is not
  green and was not represented as such. The earlier app audit remains open.

[Desktop](../audits/2026-09-08-website-redesign/desktop.png) ·
[Mobile](../audits/2026-09-08-website-redesign/mobile.png) ·
[Navigation](../audits/2026-09-08-website-redesign/navigation.png)
