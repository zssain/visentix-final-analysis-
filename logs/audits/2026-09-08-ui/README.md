# UI evidence — 2026-09-08

All figures and identities in screenshots are isolated test fixtures, not product or corpus claims. See the [audit](../2026-09-08-ui-and-app-truth.md) for findings and coverage limitations. JSON lists all 78 light captures and eight dark diagnostic checks. Only selected screenshots are retained; other screenshot names refer to temporary audit artifacts.

![Report mobile overflow](375-_reports_audit-fixture.png)
![Assessment empty and baseline states](1280-_assessments.png)
![Intake mobile](375-_intake.png)
![Workbench empty queue](1280-_workbench.png)
![Partner clients](1280-_partner.png)
![Screening empty jobs](1280-_screening.png)
![Public methodology](1280-_methodology.png)
![Assessments dark theme](dark-assessments.png)

Reproduction: run the Vite dev server on localhost with VITE_PREVIEW_SURFACES=true; use a disposable browser context with dummy session/profile localStorage, intercept every nonlocal request, and load the existing Report.test.tsx fixture for the report. Inspect at 375/768/1280px. No production identity or API is necessary. The signed-in browser check verifies rendering, not server authorization.
