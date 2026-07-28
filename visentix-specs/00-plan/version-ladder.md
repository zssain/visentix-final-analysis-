# Product Version Ladder — surface → version gating

Distinct from the engineering **release ladder** (R1–R5 in feature specs), this
records which product **version (v1…v4)** a customer-facing surface releases
with, so features don't leak into the pilot ahead of their entitlement tier.
Owner-owned. When a surface's version changes, update its route/nav guards to
match and note it here.

| Surface | Feature | Ships with | v1 (pilot) access | Note |
|---|---|---|---|---|
| `/rewrite` — Clause Rewrite | F18 | **v4 (flagship)** | `sme,admin` only | Gated away from customer for v1 (owner, 2026-07-28). Releases with **v4 entitlements**, not silently in the pilot. Backend endpoint `POST …/rewrite` also `sme,admin`. |
| `/vendors` — Vendor Due Diligence | F16 | later (mock today) | `admin` only | Still mock-backed → admin-only until rebuilt. |
| `/crosswalk` — Framework Crosswalk | F13 | later (mock today) | `admin` only | Still mock-backed → admin-only **permanently until rebuilt** (owner, 2026-07-28). |
| `/trust` — Trust Center | F15 | public when real | `admin` only | Still mock-backed → admin-only. When rebuilt to real data: report public exposure + hold for owner confirmation before it ships public. |
| `/quarterly` — Quarterly Report | F21 | **public (v1)** | public | Real (F21); serves only approved + suppressed data. Public by design. |
| `/partner` — Partner Portal | F20 | partner tier | `partner_admin,admin` | Real; customer blocked. |
| `/bulk` — Bulk Screening | F19 | contract tier | `admin` | Real; customer blocked. |

## Changelog
- 2026-07-28: Created. Recorded F18 `/rewrite` as the **v4 flagship** (sme,admin for v1). Captured the current Section-B surface gating (owner decisions). Source: owner.
