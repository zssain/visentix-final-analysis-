# F08 / F10 — Public website in the application frontend

**Status:** implemented locally, 2026-09-08; not deployed. Full backend gate
remains blocked by the pre-existing PDF determinism failure; see the
[audit](../../logs/audits/2026-09-08-ui-and-app-truth.md).

## Decision and scope

Incorporate the public website from the sibling `visentix` working tree into
`web/`, adapting its page structure to React Router and the canonical theme.
One frontend build serves the website and authenticated workspace. The sibling
working tree, including uncommitted changes, remains intact. No second package,
router, deployment, authentication mechanism, or data pipeline is introduced.

Public routes: `/`, `/platform`, `/solutions`, `/solutions/notice-assessment`,
`/solutions/quarterly-report`, `/resources`, `/about`, `/contact`.
The existing authenticated home redirect moves to `/workspace`. Existing
workspace/report URLs and role restrictions are preserved. Public pages have
their own navigation; signed-in users can visit them without the workspace rail.
The existing public methodology, finding dictionary, quarterly and legal pages
remain available through that navigation.
Signed-in visitors retain the existing background-task tracker on website pages.

## Truth and behavior

Remove unsupported scale, scores, certifications, customer/team histories,
pricing, response-time promises, publication histories and simulated success
states. Describe the four products using foundation/business-logic and the
current feature limitations. Public pages display no synthetic intelligence.
The contact page states that online requests are unavailable until a delivery
channel is configured; it collects no personal information and claims no receipt.
Resources link to existing pages rather than pretend downloads or subscriptions.
No new mock data is introduced.

Imported website heroes are a PageHeader exception; website redesign is deferred by the owner. Pages use existing tokens, keyboard-accessible navigation,
and responsive layouts. No customer data or credentials are placed in public
assets. Authentication and API authorization remain server-enforced.

## Acceptance criteria

- AC-P1 All eight public routes render without authentication at 375/768/1280px.
- AC-P2 Public navigation reaches real routes, including login; authenticated
  home redirection occurs at `/workspace`, preserving existing role landings.
- AC-P3 The workspace rail is absent on public website pages even when signed in.
- AC-P4 No invented scores, corpus totals, certifications, prices, historical
  publications, request receipts or subscription confirmations render.
- AC-P5 Existing app routes and feature masks remain intact; one `web/` build
  includes the public pages without TanStack dependencies.
- AC-P6 Document imported/adapted pages, excluded prototype content, audit
  findings and unresolved governance questions with source evidence.

## Data and migrations

None. No live DB operation, reassessment, publication, email or deployment.

## Test gate

Production frontend build; full Vitest; route/color/masking/mock/doc guards;
browser checks of public navigation, role boundaries and responsive layouts.
Run backend tests in an isolated copy with dummy configuration: the existing
live-service skips are reported explicitly, never presented as a live-data pass.

## Owner-approved website redesign — 2026-09-08

The owner subsequently approved redesign and explicitly waived the existing
website design-system and logo constraints. The DOCX inspiration contains eleven
reference images: institutional layouts, precise type, editorial serif headings,
restrained color, large footers, warm imagery and spacious dropdown navigation.
This supersedes the earlier website-redesign deferral in this amendment.

Implement an independent public-site visual layer: ivory/forest/citron palette,
typographic Visentix wordmark, responsive editorial layouts, original decorative
architectural artwork, accessible dropdown/mobile navigation, and subtle scroll
reveals respecting reduced motion. Apply it to all eight website routes. Preserve
existing application styles, authentication, routes and the truthful content
limits above. No product statistics, endorsements or publication histories are
invented. Decorative artwork is not data or an application screenshot.

Additional acceptance: all routes retain one h1; public menu works by keyboard
and closes with Escape; no horizontal overflow at mobile/tablet/desktop widths;
reduced motion shows content without movement; local preview runs with
`cd web && pnpm run dev`. Existing frontend tests and production build must pass.
The known backend PDF gate failure remains separately recorded.

## Owner-requested product and subscription revision — 2026-09-08

The owner found the first editorial redesign too simple and insufficiently
specific about technology, subscriptions and the four products. Restore the
original website's product-showcase breadth with precise product names and
commercial positioning. Keep the approved imagery and add varied colored
product panels, an interactive structural product tour, use cases, plan
comparison and clearly labeled preview/planned capabilities. Do not restore
fabricated testimonials, metrics, certifications or delivery promises.

Add public routes `/solutions/continuous-monitoring`, `/solutions/white-label`
and `/pricing`. Explain assessment access, monitoring subscriptions and partner
licensing using the four-product business model. Public price/allowance details
are not settled: the sibling prototype and foundation ranges disagree. Use
contact-for-pricing until owner details arrive; no checkout or subscription
purchase is simulated. Tour panels show product structure and explanations,
not fabricated customer findings, numeric intelligence or a claimed live demo.
No mock intelligence data is introduced.

Replace the reported broken dropdown with a click-controlled accessible
popover. Verify selecting a product with mouse/keyboard, outside dismissal,
Escape, mobile navigation and route anchors. Preserve application permissions
and test all eleven website routes at phone/tablet/desktop widths. Changes are
frontend/documentation only; no tables, migrations or billing backend changes.

Pricing clarification: owner requested keeping the old site's basic plan idea
and both plan/contact paths. Reuse Monitor / Intelligence / Enterprise names,
with prototype Monitor $299 monthly / $239 monthly-equivalent annual and
Intelligence $799 / $639 shown explicitly as **indicative planning prices**.
Enterprise remains contact pricing. This is not a committed quote, approved
allowance or working checkout. Do not reuse the prototype's unlimited claims,
seat/jurisdiction/API allowances, free-trial or guaranteed support promises.

## F08/F10 palette and login — owner-approved 2026-09-08

Switch public identity to deep navy, teal and muted gold with light neutral
surfaces. Extend the identity to the login page: typographic wordmark, matching
artwork, accessible form, password visibility and existing reset-help messaging.
Preserve signIn, error handling and protected-route/role redirects. No auth,
account provisioning, billing, schema or application-score palette changes.

## F10 workspace wordmark — owner-approved 2026-09-08

Use the new typographic Visentix identity in the desktop workspace rail and
mobile header, adapting to existing light/dark foreground tokens. The owner
also requested advice on further visual alignment; broader shell, header and
card restyling is proposed separately, not included in this logo-only change.
No changes to report branding, score semantics, authentication or data.
