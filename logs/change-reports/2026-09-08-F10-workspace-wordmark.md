# F10 — Workspace wordmark

Replaced image logos in the desktop sidebar and mobile header with the new
Arial-based typographic `visentix.` mark. Foreground inherits existing sidebar
light/dark tokens. Added `web/src/components/VisentixWordmark.tsx`, updated
`web/src/App.tsx`, and recorded owner scope in the F08/F10 amendment.

No tables, columns, migrations, authentication or report changes. Further
workspace styling is a recommendation, not implemented in this change.
Full frontend suite: 231 tests passed. Production build passed with the existing
chunk warning. Backend is unchanged; earlier PDF determinism issue remains open.
Preview: `cd web && pnpm run dev`, http://localhost:5173/workspace.
This change remains local and unpushed.
