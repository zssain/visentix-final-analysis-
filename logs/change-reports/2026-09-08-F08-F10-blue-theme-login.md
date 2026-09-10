# F08/F10 — Navy, teal and gold identity + login

Owner-approved public palette revision and matching login redesign. Website
surfaces now use navy structure, teal actions and muted-gold highlights. Login
uses the typographic wordmark, original architectural artwork, a responsive form,
password visibility control, administrator reset guidance and plan-access link.
Existing signIn behavior, rejection handling and role redirects are preserved.

Files: `web/src/theme.css`, public `website.css` / `product-site.css`, website
favicon, `web/src/pages/Login.tsx`, new `web/src/pages/login.css`, F08 amendment,
this report and decision log. No tables, columns, migrations, backend changes or
new packages. The signed-in application's score/theme tokens are unchanged.

Validation: 231 frontend tests passed, production build and `make guards` passed.
Chromium checked home/login at 375/1440px: no overflow or page errors. Password
visibility, reset help and rejected-login/retry state were checked with an
intercepted 401 fixture; no live credentials were submitted. The previously
reported backend PDF determinism issue remains open; backend code is unchanged.

Preview remains running: `cd web && pnpm run dev`, http://localhost:5173/ and
http://localhost:5173/login. Changes remain local, not deployed or pushed.
