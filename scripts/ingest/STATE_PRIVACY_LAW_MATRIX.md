# US State Comprehensive Consumer Privacy Law — Coverage Matrix

**Compiled:** 2026-08-18 · **Status:** DRAFT — awaiting SME sign-off before ingestion
**Purpose:** Source-of-truth for completing `scripts/ingest/ingest_state_laws.py` (`NEW_STATE_LAWS`)
and `config/targets.yaml` (jurisdiction weights) to full 50-state + DC coverage.

Every fact below was verified this session against primary/authoritative sources (state codes,
state AG pages, official legislature bill text) cross-checked against the IAPP US State Privacy
Legislation Tracker. Items that could not be confirmed at a primary source are flagged UNVERIFIED.

Requirement strings map to the 14 `requirement_type` values already used by `obligation` rows.

---

## 1. Summary

| Bucket | Count | Jurisdictions |
|---|---|---|
| Comprehensive law **in effect** | 20 | CA, CO, CT, DE, FL, IA, IN, KY, MD, MN, MT, NE, NH, NJ, OR, RI, TN, TX, UT, VA |
| Comprehensive law **signed, not yet effective** | 4 | AL (2027-05-01), LA (2027-01-01), OK (2027-01-01), VT (2028-01-01) |
| **No** comprehensive law | 26 + DC | AK, AZ, AR, GA, HI, ID, IL, KS, ME, MA, MI, MS, MO, NV, NM, NY, NC, ND, OH, PA, SC, SD, WA, WI, WV, WY, DC |

Of the 24 comprehensive-law states, **11 are already modeled** in `ingest_state_laws.py`
(FL, IA, IN, KY, MD, MN, MT, NE, NH, RI, TN). This matrix adds **13 new** (9 in-effect + 4 pending)
and **corrects 1** (NE).

---

## 2. Comprehensive laws IN EFFECT (20)

Legend for rights columns: A=access Del=deletion C=correction P=portability Ap=appeal
Sale=opt-out sale/share TA=opt-out targeted-ad Prof=profiling opt-out(ai_profiling_optout)
Sens=sensitive-data consent N=notice Ret=retention-disclosure UOOM=universal opt-out signal
Kids=children's-data restrictions PRA=private right of action

| St | Law | Citation | Effective | Threshold (plain) | A|Del|C|P|Ap | Sale|TA|Prof | Sens|N|Ret|UOOM|Kids|PRA | In DB? | Source |
|----|-----|----------|-----------|-------------------|---|---|---|---|---|
| CA | CCPA/CPRA | Cal. Civ. Code §§1798.100–1798.199.100 | 2020-01-01 (CPRA 2023-01-01) | $25M rev OR 100k consumers/hh OR 50% rev from sell/share | ✅✅✅✅❌ | ✅(sale/share)|—|✅ | ✅|✅|✅|✅|✅|✅**breach-only** | **NEW** | leginfo; cppa.ca.gov |
| VA | VCDPA | Va. Code §§59.1-575–585 | 2023-01-01 | 100k OR 25k+50%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|❌|❌|❌ | weight only → **NEW** | law.lis.virginia.gov |
| CO | CPA | C.R.S. §§6-1-1301–1314 | 2023-07-01 | 100k OR 25k+rev-from-sale | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|✅|❌ | weight only → **NEW** | coag.gov |
| CT | CTDPA | Conn. Gen. Stat. §§42-515–525 (PA 22-15) | 2023-07-01 | 100k OR 25k+25%rev ⚠️PA25-113 → 35k eff 2026-07-01 | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|✅|❌ | weight only → **NEW** | portal.ct.gov/ag |
| UT | UCPA | Utah Code §§13-61-101–404 | 2023-12-31 | $25M rev AND (100k OR 25k+50%rev) | ✅✅✅(2026-07-01)✅❌ | ✅|✅|❌ | ❌(notice+opt-out)|✅|❌|❌|✅|❌ | **NEW** | le.utah.gov |
| OR | OCPA | ORS 646A.570–589 (SB619) | 2024-07-01 (nonprofits 2025-07-01) | 100k OR 25k+25%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅(2026-01-01)|✅|❌ | **NEW** | oregonlegislature.gov; doj.state.or.us |
| TX | TDPSA | Tex. Bus.&Com. Code ch.541 (HB4) | 2024-07-01 (UOOM 2025-01-01) | SBA "not a small business" — **no numeric threshold** | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|✅|❌ | weight only → **NEW** | capitol.texas.gov |
| MT | MCDPA | Mont. Code §§30-14-2801–2817 | 2024-10-01 | 50k consumers | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|❌|❌ | ✅ in DB | leg.mt.gov |
| FL | FDBR | Fla. Stat. §§501.701–721 | 2024-07-01 | $1B rev + platform criteria | ✅✅✅✅❌ | ✅|✅|✅ | ✅|✅|❌|❌|✅|❌ | ✅ in DB | flsenate.gov |
| IA | ICDPA | Iowa Code §§715D.1–8 | 2025-01-01 | 100k OR 25k+50%rev | ✅✅❌✅❌ | ✅|✅|❌ | ✅|✅|❌|❌|❌|❌ | ✅ in DB | legis.iowa.gov |
| NE | NDPA | Neb. Rev. Stat. §§87-1101–1130 (LB1074) | 2025-01-01 | SBA "not a small business" — no numeric threshold | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|❌**cond.**|✅|❌ | ✅ in DB **(FIX: add Kids; UOOM stays OUT; cite →1130)** | AG protectthegoodlife.nebraska.gov |
| NH | NHDPA | N.H. RSA ch. 507-H | 2025-01-01 | 35k OR 10k+25%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|❌|❌ | ✅ in DB | gencourt.state.nh.us |
| DE | DPDPA | Del. Code tit.6 §§12D-101–111 | 2025-01-01 (UOOM 2026-01-01) | 35k OR 10k+20%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|✅|❌ | **NEW** | delcode.delaware.gov |
| NJ | NJDPA | N.J. Stat. §56:8-166.4 et seq (S332) | 2025-01-15 (UOOM ~2025-07-15) | 100k OR 25k+rev-from-sale | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|✅|✅|❌ | **NEW** | njleg.state.nj.us |
| MN | MNCDPA | Minn. Stat. §§325O.01–16 | 2025-07-31 | 100k OR 25k+25%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|✅|✅|✅|❌ | ✅ in DB | revisor.mn.gov |
| MD | MODPA | Md. Com. Law §§14-4601–4616 | 2025-10-01 | 35k residents | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|✅|✅|✅|❌ | ✅ in DB | mgaleg.maryland.gov |
| TN | TIPA | Tenn. Code §§47-18-3201–3213 | 2025-07-01 | $25M rev AND (175k OR 25k+50%rev) | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|❌|❌|❌ | ✅ in DB | capitol.tn.gov |
| IN | INCDPA | Ind. Code §§24-15-1–16 | 2026-01-01 | 100k OR 25k+50%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|✅|✅|❌|❌ | ✅ in DB | iga.in.gov |
| KY | KCDPA | Ky. Rev. Stat. §§367.400–499 | 2026-01-01 | 100k OR 25k+50%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|❌|❌|❌|❌ | ✅ in DB | legislature.ky.gov |
| RI | RIDTPPA | R.I. Gen. Laws §§6-48.1-1–15 | 2026-01-01 | 35k OR 10k+20%rev | ✅✅✅✅✅ | ✅|✅|✅ | ✅|✅|✅|✅|❌|❌ | ✅ in DB | rilegislature.gov |

### Notes on in-effect set
- **CA** is the only state with any **private right of action** (§1798.150, data-breach only). Its
  sensitive-data model is a right-to-*limit* (opt-out), mapped to `sensitive_data_consent` as the
  nearest string; ADMT/profiling opt-out reg effective 2026-01-01, enforcement phases to 2027-01-01.
- **VA has NO universal-opt-out mandate** — verified against the Virginia Code (many secondary
  trackers wrongly claim one).
- **NE correction:** existing DB entry is right to EXCLUDE `universal_optout_signal` (only a
  conditional/derivative duty under §87-1111 — IAPP & DWT exclude NE from UOOM-mandate states), but
  it is MISSING `childrens_data_restrictions` (known-child data = sensitive). Citation should be
  §§87-1101–1130 (script currently says –1116).
- `retention_disclosure` is only clearly granted by **CA, MN, MD, IN, RI** (newer-generation notice
  requirements). Older VA-model laws (VA/CO/CT/UT/TX/OR/DE/NJ/NE/TN/KY/NH/MT/IA/FL) do **not** carry
  an explicit retention-disclosure mandate — kept conservative.

---

## 3. Comprehensive laws SIGNED, NOT YET EFFECTIVE (4)

| St | Law | Citation / Bill | Signed | Effective | Threshold | Notes | Source |
|----|-----|-----------------|--------|-----------|-----------|-------|--------|
| OK | OKCDPA | SB 546 | 2026-03-20 | 2027-01-01 | 100k OR 25k+50%rev | VCDPA-model; access/C/Del/P + appeal; opt-out sale/TA/profiling; AG-only, permanent cure. **NOT the defunct HB 1602.** | mayerbrown; okhouse.gov |
| AL | APDPA | HB 351 | 2026-04-17 | 2027-05-01 | 25k consumers OR 25% rev from sale | VCDPA-model; access/C/Del/P; opt-out TA/sale/profiling; **no appeal right**; AG-enforced | DLA Piper; Hunton; legiscan AL HB351 |
| LA | LDPA | SB 386 / Act 502 | 2026-05-29 | 2027-01-01 | $25M rev OR 75k consumers OR 50% rev from sale | VCDPA-model; access/C/Del/P; opt-out TA/sale/profiling; sensitive opt-in; UOOM; cure sunsets 2027-07-31. Act 502 # UNVERIFIED at primary source | Troutman; Hunton; WilmerHale |
| VT | VDPOSA | S.71 / Act 145 | 2026-06-16 | 2028-01-01 | 35k consumers | Successor to vetoed 2024 H.121; adds AI/LLM-training disclosure; PRA dropped from comprehensive framework | legislature.vermont.gov; insideprivacy |

**SME DECISION:** load these now (with future `effective_date`, so the pipeline treats them as
not-yet-verified/future) or hold until closer to effect? Recommended: **load now** — `effective_date`
already drives the "verified" gate in `evidence.py`, and clients assessing multi-state exposure
benefit from seeing upcoming obligations.

---

## 4. NO comprehensive law (26 + DC)

All have data-breach-notification statutes (Phase 2). "pending" = a comprehensive bill is live but
not enacted. Sector laws noted where notable.

| St | Status | Notable pending bill / sector law |
|----|--------|-----------------------------------|
| AK | pending | HB 367 (Consumer Data Privacy Act), in House Finance 2026 |
| AZ | pending | SB 1815, in Senate 2026 |
| AR | **none** (contested) | SB 258 "Data Care Act/DRSTA" eff 2026-07-01 — some call comprehensive+AI; **IAPP/MultiState EXCLUDE**. Breach law + kids' law are separate. Default: exclude, flag. |
| GA | **none** | ⚠️ SB 111 privacy title was **gutted → rural-hospital tax credit**; tracker trap |
| HI | none | SB3016/SB1163 died 2026 |
| ID | none | only sector bills (social media, AI) |
| IL | none | **BIPA/GIPA sector-only**; SB2875/SB3548 died 2026 |
| KS | none | Age-Appropriate Design Code only |
| ME | none | LD 1822 passed both chambers separately, died in reconciliation 2026-04 |
| MA | **pending (closest)** | S2619/H5479 — passed both chambers, **in conference committee** — WATCH |
| MI | pending | SB 359, stalled in Committee of the Whole |
| MS | none | HB 1051 died 2026-02 |
| MO | none | biometric/AI bills only |
| NV | none | biennial; NRS 603A (notice) + SB370 (health) sector-only |
| NM | none | SB 53 (CHISPA) died 2026-02 |
| NY | pending | S3044 (NY Privacy Act); **SHIELD Act = breach/security, not comprehensive** (existing 0.7 weight is for that) |
| NC | pending | HB 462 / SB 757 in committee |
| ND | none | HB 1127 = financial-institution security only (excluded); biennial, next 2027 |
| OH | none | only a govt-agency data bill |
| PA | pending | HB 78 passed House, in Senate committee |
| SC | pending (stalled) | H 3401 in House Judiciary |
| SD | none | genetic/social-media/ISP bills only |
| WA | none / pending | **My Health My Data = sector-only** (existing 0.5 weight is for that); HB 1671 pending |
| WI | none | AB172/SB166 died 2026-03 |
| WV | none | HB 2987 died in Senate 2025 |
| WY | none | SF0020 covers government entities only |
| DC | none | only health-only (B26-0525) & govt-only (B26-0670) bills |

---

## 5. Tracker traps caught (deliberately kept OUT of the data)

1. **GA "Consumer Privacy Protection Act"** — enrolled SB 111 text is a rural-hospital tax credit;
   privacy content was stripped in the House. Many trackers still show it as a signed privacy law.
2. **AR "APDPA"** — a phantom law repeated on AI-generated sites; real AR statutes are a breach law +
   a children's law. SB 258 is genuinely contested (see §4).
3. **OK HB 1602** — the defunct "Computer Data Privacy Act" that died for years; the real enacted law
   is **SB 546**. Some trackers still surface the stale HB 1602 title.
4. **ND HB 1127** — financial-institution security (GLBA-model), not comprehensive.
5. **Sector ≠ comprehensive** — IL BIPA, WA MHMD, NY SHIELD are sector/breach laws; excluded from the
   comprehensive set (but their existing jurisdiction weights stay).

---

## 6. Open decisions for SME sign-off

| # | Decision | Recommendation |
|---|----------|----------------|
| D1 | Load the 4 signed-not-yet-effective laws (AL, LA, OK, VT) now? | **Yes**, with future `effective_date` |
| D2 | Treat AR SB 258 as comprehensive? | **No** — follow IAPP; keep as "none", note contested |
| D3 | CT threshold — store original (100k) or PA 25-113 amended (35k, eff 2026-07-01)? | Store **amended 35k** (in force as of now); note original in summary |
| D4 | Jurisdiction weights for the ~40 newly-added states (see §7) | SME to confirm proposed tiers |
| D5 | Phase 2: breach-notification (all 50) + sector (BIPA/MHMD) — needs new `requirement_type`/domain via **spec-update** workflow (ref OD-06: breach `security_event` currently excluded from scoring) | Scope separately after Phase 1 lands |
| D6 | NE fix (add Kids, correct citation) | Apply with Phase 1 |

---

## 7. Proposed jurisdiction weights (config/targets.yaml) — DRAFT for SME

Rationale: keep existing weights; give in-effect comprehensive-law states a mid tier (0.5), the most
active/large enforcers a higher tier, signed-not-yet-effective 0.4, no-comprehensive-law states the
existing 0.3 default (NY/WA keep their sector weights).

```
Existing (unchanged): US-FED 0.9, US-CA 1.0, US-TX 0.7, US-CT 0.5, US-CO 0.6, US-WA 0.5,
                      US-VA 0.5, US-NY 0.7, EU 0.8
In-effect comprehensive (propose 0.5): US-UT, US-OR, US-MT, US-FL, US-IA, US-NE, US-NH, US-DE,
                      US-NJ, US-MN, US-MD, US-TN, US-IN, US-KY, US-RI
Signed-not-yet-effective (propose 0.4): US-AL, US-LA, US-OK, US-VT
All others: inherit default 0.30
```

---

## 8. Ready-to-ingest data

The 13 new `NEW_STATE_LAWS` entries (9 in-effect + 4 pending) and the NE fix are prepared to drop
into `scripts/ingest/ingest_state_laws.py`. They follow the exact existing dict shape and reuse the
14 requirement strings, so `build_obligation_rows()` / `build_legal_ref_row()` and the deterministic
UUID upsert work unchanged (idempotent). Applying them is a one-line list extension + one edit to the
NE entry. **Not yet applied — awaiting sign-off on D1–D6.**
