# F08 — Product and subscription website revision

Replaced the sparse editorial homepage with a product-led website: four precise
product offerings, colored product illustrations, interactive structural tours,
role-based use cases, plans, and explicitly labeled preview/planned capabilities.
Kept the architectural artwork and editorial identity. Replaced navigation with
click-controlled Radix popovers; selecting a product, Escape and outside dismissal
were verified in Chromium. Added dedicated monitoring, white-label and pricing
pages, bringing the public website to eleven routes.

The owner requested the original Monitor / Intelligence / Enterprise plan idea
and both plan/contact paths. Prices from that prototype are marked indicative;
monthly/annual selection updates them and carries interest to Contact. No purchase,
message, customer result or intelligence value is simulated. Final commercial
scope still needs confirmation.

Files: public page components, `products.ts`, `ProductShowcase.tsx`,
`ProductDetail.tsx`, `WebsiteNavigation.tsx`, `product-site.css`, cleaned obsolete
rules from `website.css`, public color tokens, App routes/registry, website tests,
F08 amendment and route table. No tables, columns, migrations, backend or billing
changes; no packages installed.

Validation: 231 frontend tests passed; production build passed (existing chunk
warning). Chromium checked eleven routes at 375/768/1440px: one h1, no horizontal
overflow, no uncaught page errors. Product dropdown selection, dismissal, product
tour switching, annual plan pricing and selected-plan contact context passed.
Prior backend PDF determinism failure remains open; backend code is unchanged.

Run `cd web && pnpm run dev`. The existing preview remains at
http://localhost:5173/. Changes are local, not deployed or pushed.
