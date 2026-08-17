"""Ingest state comprehensive privacy laws for missing jurisdictions.

Adds obligation rows (one per requirement_type per law) and legal_reference rows
for every US state with a comprehensive consumer privacy law. Uses OpenStates API
to locate bill URLs where possible; falls back to hardcoded official URLs.

Coverage (as of 2026-08-18, verified vs primary sources — see
scripts/ingest/STATE_PRIVACY_LAW_MATRIX.md for citations and open decisions):
  * 20 comprehensive laws IN EFFECT.
  * 4 comprehensive laws SIGNED but NOT YET EFFECTIVE (AL, LA, OK 2027; VT 2028),
    loaded with future effective_date. [D1]
  * 26 states + DC have no comprehensive law (weights only; Phase 2 = breach/sector).
Open SME decisions are flagged inline as [D1]-[D3]; Arkansas SB 258 is excluded [D2].

Idempotent: upserts on obligation_id and reference_id.

Usage:
    PYTHONPATH=. python scripts/ingest/ingest_state_laws.py
"""

import logging
import time
import uuid

import httpx

from scripts.ingest._common import (
    OPENSTATES_API_KEY,
    finish_run,
    sha256_text,
    start_run,
    upsert,
)

log = logging.getLogger("ingest.state_laws")

# ────────────────────────────────────────────────────────────
# The 14 requirement_types used by existing obligations
# ────────────────────────────────────────────────────────────

REQUIREMENT_TYPES = [
    "consumer_rights_access",
    "consumer_rights_deletion",
    "consumer_rights_correction",
    "consumer_rights_portability",
    "consumer_rights_appeal",
    "opt_out_sale_share",
    "opt_out_targeted_advertising",
    "sensitive_data_consent",
    "notice_requirement",
    "retention_disclosure",
    "universal_optout_signal",
    "ai_profiling_optout",
    "childrens_data_restrictions",
    "private_right_of_action",
]

# ────────────────────────────────────────────────────────────
# New state laws to ingest (11 states not in DB)
# ────────────────────────────────────────────────────────────

NEW_STATE_LAWS = [
    {
        "jurisdiction": "IN",
        "state_name": "Indiana",
        "law": "INCDPA",
        "framework": "INCDPA",
        "reference_id": "INCDPA-IN",
        "citation": "Ind. Code §§ 24-15-1 to 24-15-16",
        "title": "Indiana Consumer Data Protection Act",
        "summary": "Indiana's comprehensive consumer data privacy law granting residents rights to access, correct, delete, and obtain personal data, and to opt out of targeted advertising, sale, and profiling. Effective January 1, 2026.",
        "effective_date": "2026-01-01",
        "official_url": "https://iga.in.gov/legislative/2023/bills/senate/5",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        # Which of the 14 requirement_types this law mandates
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement", "retention_disclosure",
            "universal_optout_signal", "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "KY",
        "state_name": "Kentucky",
        "law": "KCDPA",
        "framework": "KCDPA",
        "reference_id": "KCDPA-KY",
        "citation": "Ky. Rev. Stat. §§ 367.400 to 367.499",
        "title": "Kentucky Consumer Data Protection Act",
        "summary": "Kentucky's comprehensive data privacy law granting consumers rights to access, correct, delete, and obtain personal data, and to opt out of targeted advertising, sale of data, and profiling.",
        "effective_date": "2026-01-01",
        "official_url": "https://apps.legislature.ky.gov/record/24RS/hb15.html",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "RI",
        "state_name": "Rhode Island",
        "law": "RIDPA",
        "framework": "RIDPA",
        "reference_id": "RIDPA-RI",
        "citation": "R.I. Gen. Laws §§ 6-48.1-1 to 6-48.1-15",
        "title": "Rhode Island Data Transparency and Privacy Protection Act",
        "summary": "Rhode Island's comprehensive privacy law granting consumers rights to access, delete, correct, and obtain data. Requires data protection assessments and recognizes universal opt-out signals.",
        "effective_date": "2026-01-01",
        "official_url": "https://webserver.rilegislature.gov/BillText/BillText24/HouseText24/H7787A.pdf",
        "applicability": "35K+ consumers OR 10K+ consumers + >20% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement", "retention_disclosure",
            "universal_optout_signal", "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "MD",
        "state_name": "Maryland",
        "law": "MODPA",
        "framework": "MODPA",
        "reference_id": "MODPA-MD",
        "citation": "Md. Code, Com. Law §§ 14-4601 to 14-4616",
        "title": "Maryland Online Data Privacy Act",
        "summary": "Maryland's comprehensive privacy law with strong data minimization requirements. Restricts targeted advertising to minors and requires consent for processing sensitive data. Prohibits sale of sensitive data entirely.",
        "effective_date": "2025-10-01",
        "official_url": "https://mgaleg.maryland.gov/mgawebsite/Legislation/Details/sb0541?ys=2024RS",
        "applicability": "Controllers processing data of 35K+ Maryland residents",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement", "retention_disclosure",
            "universal_optout_signal", "ai_profiling_optout",
            "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "MN",
        "state_name": "Minnesota",
        "law": "MNCDPA",
        "framework": "MNCDPA",
        "reference_id": "MNCDPA-MN",
        "citation": "Minn. Stat. §§ 325O.01 to 325O.16",
        "title": "Minnesota Consumer Data Privacy Act",
        "summary": "Minnesota's comprehensive privacy law granting consumers rights to access, delete, correct, and obtain personal data. Includes protections for minors and requires data protection assessments for high-risk processing.",
        "effective_date": "2025-07-31",
        "official_url": "https://www.revisor.mn.gov/bills/text.php?number=HF2309&type=bill&version=3&session=ls93&session_year=2024&session_number=0",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >25% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement", "retention_disclosure",
            "universal_optout_signal", "ai_profiling_optout",
            "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "MT",
        "state_name": "Montana",
        "law": "MCDPA",
        "framework": "MCDPA",
        "reference_id": "MCDPA-MT",
        "citation": "Mont. Code Ann. §§ 30-14-2801 to 30-14-2817",
        "title": "Montana Consumer Data Privacy Act",
        "summary": "Montana's comprehensive data privacy law modeled after Connecticut's CTDPA. Grants consumers rights to access, correct, delete, and obtain data, with opt-out rights for targeted advertising and data sales.",
        "effective_date": "2024-10-01",
        "official_url": "https://leg.mt.gov/bills/2023/billhtml/SB0384.htm",
        "applicability": "50K+ consumers/yr (lower threshold reflecting smaller population)",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "NE",
        "state_name": "Nebraska",
        "law": "NEDPA",
        "framework": "NEDPA",
        "reference_id": "NEDPA-NE",
        "citation": "Neb. Rev. Stat. §§ 87-1101 to 87-1130",
        "title": "Nebraska Data Privacy Act",
        "summary": "Nebraska's comprehensive privacy law granting consumers rights to access, delete, correct, and obtain data. Modeled closely after the Texas TDPSA with adjustments for Nebraska's regulatory framework.",
        "effective_date": "2025-01-01",
        "official_url": "https://nebraskalegislature.gov/bills/view_bill.php?DocumentID=55553",
        "applicability": "Not a small business (SBA def) unless selling sensitive data",
        # NOTE (2026-08-18): NE does NOT independently mandate universal_optout_signal — §87-1111 is
        # only a conditional/derivative duty; IAPP & DWT exclude NE from UOOM-mandate states. Kept out.
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "NH",
        "state_name": "New Hampshire",
        "law": "NHDPA",
        "framework": "NHDPA",
        "reference_id": "NHDPA-NH",
        "citation": "N.H. Rev. Stat. Ann. §§ 507-H:1 to 507-H:16",
        "title": "New Hampshire Privacy Act",
        "summary": "New Hampshire's comprehensive data privacy law granting consumers rights to access, correct, delete, and obtain personal data. Requires recognition of universal opt-out mechanisms.",
        "effective_date": "2025-01-01",
        "official_url": "https://gencourt.state.nh.us/bill_status/legacy/bs2016/billText.aspx?sy=2024&id=1427&txtFormat=html",
        "applicability": "35K+ consumers OR 10K+ consumers + >25% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "IA",
        "state_name": "Iowa",
        "law": "ICDPA",
        "framework": "ICDPA",
        "reference_id": "ICDPA-IA",
        "citation": "Iowa Code §§ 715D.1 to 715D.8",
        "title": "Iowa Consumer Data Protection Act",
        "summary": "Iowa's comprehensive data privacy law granting consumers rights to access, delete, and obtain personal data. More business-friendly with no data protection assessment requirement and no universal opt-out signal mandate.",
        "effective_date": "2025-01-01",
        "official_url": "https://www.legis.iowa.gov/legislation/BillBook?ga=90&ba=SF%20262",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion",
            "consumer_rights_portability",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
        ],
    },
    {
        "jurisdiction": "TN",
        "state_name": "Tennessee",
        "law": "TIPA",
        "framework": "TIPA",
        "reference_id": "TIPA-TN",
        "citation": "Tenn. Code Ann. §§ 47-18-3201 to 47-18-3213",
        "title": "Tennessee Information Protection Act",
        "summary": "Tennessee's comprehensive data privacy law granting consumers rights to access, correct, delete, and obtain personal data. Includes a unique affirmative defense provision for controllers with privacy programs conforming to NIST frameworks.",
        "effective_date": "2025-07-01",
        "official_url": "https://wapp.capitol.tn.gov/apps/BillInfo/Default.aspx?BillNumber=HB1181&GA=113",
        "applicability": "25M+ revenue AND 175K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "FL",
        "state_name": "Florida",
        "law": "FDBR",
        "framework": "FDBR",
        "reference_id": "FDBR-FL",
        "citation": "Fla. Stat. §§ 501.701 to 501.721",
        "title": "Florida Digital Bill of Rights",
        "summary": "Florida's comprehensive data privacy law applying to large businesses. Grants consumers rights to access, delete, and correct personal data, with specific protections for children under 18. Higher revenue threshold than most state laws.",
        "effective_date": "2024-07-01",
        "official_url": "https://www.flsenate.gov/Session/Bill/2023/262",
        "applicability": "$1B+ global revenue AND meet one of: 50%+ online ad revenue, operate consumer smart speaker/voice assistant, or operate app store with 250K+ apps",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },

    # ════════════════════════════════════════════════════════════════════════
    #  ADDED 2026-08-18 — verified vs primary sources; see STATE_PRIVACY_LAW_MATRIX.md.
    #  Section A: comprehensive laws IN EFFECT (9 states not previously modeled).
    #  Open decisions flagged inline: [D2] Arkansas, [D3] CT threshold.
    # ════════════════════════════════════════════════════════════════════════
    {
        "jurisdiction": "CA",
        "state_name": "California",
        # Aligned to the existing DB row (reference_id CCPA-CPRA, law "CCPA/CPRA")
        # so re-runs refresh it in place instead of creating a duplicate. The codex
        # (finding_legal_reference) links all 8 finding types to CCPA-CPRA.
        "law": "CCPA/CPRA",
        "framework": "CCPA/CPRA",
        "reference_id": "CCPA-CPRA",
        "citation": "Cal. Civ. Code §§ 1798.100 to 1798.199.100",
        "title": "California Consumer Privacy Act of 2018 (as amended by the California Privacy Rights Act of 2020)",
        "summary": "California's comprehensive privacy law granting rights to know/access, delete, correct, and port personal information, opt out of sale/sharing, and limit sensitive-data use. Enforced by the CPPA and AG. Effective 2020-01-01; CPRA amendments operative 2023-01-01.",
        "effective_date": "2020-01-01",
        "official_url": "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5",
        "applicability": "$25M+ annual revenue OR buys/sells/shares data of 100K+ consumers/households OR 50%+ revenue from selling/sharing personal information",
        # Only state with any private_right_of_action (breach-only, §1798.150). No VCDPA-style appeal.
        # ADMT/profiling opt-out reg effective 2026-01-01 (enforcement phases to 2027-01-01).
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability",
            "opt_out_sale_share",
            "sensitive_data_consent", "notice_requirement", "retention_disclosure",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
            "private_right_of_action",
        ],
    },
    {
        "jurisdiction": "VA",
        "state_name": "Virginia",
        "law": "VCDPA",
        "framework": "VCDPA",
        "reference_id": "VCDPA-VA",
        "citation": "Va. Code §§ 59.1-575 to 59.1-585",
        "title": "Virginia Consumer Data Protection Act",
        "summary": "The original VCDPA-model law: rights to access, correct, delete, port, and appeal, plus opt-out of sale, targeted advertising, and profiling. Opt-in consent for sensitive data. AG-exclusive enforcement; no private right of action.",
        "effective_date": "2023-01-01",
        "official_url": "https://law.lis.virginia.gov/vacodefull/title59.1/chapter53/",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        # Verified vs primary source: VCDPA has NO universal_optout mandate (common tracker error).
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "CO",
        "state_name": "Colorado",
        "law": "CPA",
        "framework": "CPA",
        "reference_id": "CPA-CO",
        "citation": "Colo. Rev. Stat. §§ 6-1-1301 to 6-1-1314",
        "title": "Colorado Privacy Act",
        "summary": "Comprehensive law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Requires honoring a Universal Opt-Out Mechanism (GPC, mandatory since 2024-07-01). SB 24-041 added minors' protections (2025-10-01). AG + DAs enforce; no private right of action.",
        "effective_date": "2023-07-01",
        "official_url": "https://coag.gov/resources/colorado-privacy-act/",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "CT",
        "state_name": "Connecticut",
        "law": "CTDPA",
        "framework": "CTDPA",
        "reference_id": "CTDPA-CT",
        "citation": "Conn. Gen. Stat. §§ 42-515 to 42-525 (Public Act 22-15)",
        "title": "Connecticut Data Privacy Act",
        "summary": "Comprehensive law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Honors universal opt-out signals (since 2025-01-01); minors' protections via PA 23-56. AG-exclusive enforcement; no private right of action.",
        "effective_date": "2023-07-01",
        # [D3] Threshold below is the ORIGINAL (100K / 25K+25%). PA 25-113 LOWERED it to 35,000 and
        # removed the revenue prong, effective 2026-07-01 (in force now). SME: confirm which to store.
        "applicability": "35K+ consumers (PA 25-113, eff. 2026-07-01; originally 100K OR 25K + >25% revenue from data sale)",
        "official_url": "https://portal.ct.gov/ag/sections/privacy/the-connecticut-data-privacy-act",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "UT",
        "state_name": "Utah",
        "law": "UCPA",
        "framework": "UCPA",
        "reference_id": "UCPA-UT",
        "citation": "Utah Code §§ 13-61-101 to 13-61-404",
        "title": "Utah Consumer Privacy Act",
        "summary": "The most business-friendly state privacy law: rights to access, delete, and port data, plus opt-out of sale and targeted advertising. HB 418 added a correction right (effective 2026-07-01). Uses notice-and-opt-out (not opt-in) for sensitive data. No appeal, no universal opt-out, no profiling opt-out, no private right of action.",
        "effective_date": "2023-12-31",
        "official_url": "https://le.utah.gov/~2022/bills/sbillint/SB0227.htm",
        "applicability": "$25M+ revenue AND (100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale)",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "notice_requirement", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "OR",
        "state_name": "Oregon",
        "law": "OCPA",
        "framework": "OCPA",
        "reference_id": "OCPA-OR",
        "citation": "ORS 646A.570 to 646A.589 (Oregon Laws 2023, ch. 369)",
        "title": "Oregon Consumer Privacy Act",
        "summary": "Comprehensive law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Uniquely, consumers may request a list of the SPECIFIC third parties that received their data. Universal opt-out mandatory 2026-01-01. AG-exclusive enforcement; no private right of action.",
        "effective_date": "2024-07-01",
        "official_url": "https://olis.oregonlegislature.gov/liz/2023R1/Measures/Overview/SB619",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >25% revenue from data sale (nonprofits from 2025-07-01)",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "TX",
        "state_name": "Texas",
        "law": "TDPSA",
        "framework": "TDPSA",
        "reference_id": "TDPSA-TX",
        "citation": "Tex. Bus. & Com. Code ch. 541 (§§ 541.001 to 541.205)",
        "title": "Texas Data Privacy and Security Act",
        "summary": "Comprehensive law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Uniquely keys applicability to the federal SBA small-business definition (no numeric threshold) and mandates verbatim notice text when selling sensitive/biometric data. Universal opt-out from 2025-01-01. No private right of action.",
        "effective_date": "2024-07-01",
        "official_url": "https://capitol.texas.gov/tlodocs/88R/billtext/html/HB00004F.htm",
        "applicability": "Conducts business in TX + processes/sells personal data + is NOT a small business (federal SBA definition) — no consumer-count or revenue threshold",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "DE",
        "state_name": "Delaware",
        "law": "DPDPA",
        "framework": "DPDPA",
        "reference_id": "DPDPA-DE",
        "citation": "Del. Code tit. 6, §§ 12D-101 to 12D-111",
        "title": "Delaware Personal Data Privacy Act",
        "summary": "Comprehensive law with one of the lowest applicability thresholds. Grants access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Opt-in consent for sensitive data; universal opt-out honored from 2026-01-01. Delaware DOJ enforces; no private right of action.",
        "effective_date": "2025-01-01",
        "official_url": "https://delcode.delaware.gov/title6/c012d/index.html",
        "applicability": "35K+ consumers OR 10K+ consumers + >20% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
    {
        "jurisdiction": "NJ",
        "state_name": "New Jersey",
        "law": "NJDPA",
        "framework": "NJDPA",
        "reference_id": "NJDPA-NJ",
        "citation": "N.J. Stat. Ann. § 56:8-166.4 et seq. (P.L. 2023, c. 266)",
        "title": "New Jersey Data Privacy Act",
        "summary": "Comprehensive law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Opt-in consent for sensitive data (incl. financial data) and for consumers 13-16. Universal opt-out honored ~2025-07-15. AG/Division of Consumer Affairs enforce; no private right of action.",
        "effective_date": "2025-01-15",
        "official_url": "https://www.njleg.state.nj.us/bill-search/2022/S332",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },

    # ════════════════════════════════════════════════════════════════════════
    #  Section B: comprehensive laws SIGNED but NOT YET EFFECTIVE. [D1]
    #  Loaded now with FUTURE effective_date (the effective_date drives the
    #  "verified" gate in evidence.py). Rights are per law-firm summaries of the
    #  enrolled bills; RE-VERIFY against codified text before each effective date.
    #  ([D2] Arkansas SB 258 is deliberately EXCLUDED — IAPP/MultiState do not
    #  count it as comprehensive; revisit if the SME decides otherwise.)
    # ════════════════════════════════════════════════════════════════════════
    {
        "jurisdiction": "OK",
        "state_name": "Oklahoma",
        "law": "OKCDPA",
        "framework": "OKCDPA",
        "reference_id": "OKCDPA-OK",
        "citation": "Oklahoma Consumer Data Privacy Act, SB 546 (2026) — codification pending",
        "title": "Oklahoma Consumer Data Privacy Act",
        "summary": "SIGNED 2026-03-20, EFFECTIVE 2027-01-01. VCDPA-model law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Business-friendly (high thresholds, permanent cure period). NOT the defunct HB 1602. AG-exclusive enforcement.",
        "effective_date": "2027-01-01",
        "official_url": "https://legiscan.com/OK/bill/SB546/2026",
        "applicability": "100K+ consumers/yr OR 25K+ consumers + >50% revenue from data sale",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "AL",
        "state_name": "Alabama",
        "law": "APDPA",
        "framework": "APDPA",
        "reference_id": "APDPA-AL",
        "citation": "Alabama Personal Data Protection Act, HB 351 (2026) — codification pending",
        "title": "Alabama Personal Data Protection Act",
        "summary": "SIGNED 2026-04-17, EFFECTIVE 2027-05-01. VCDPA-model law granting access, correction, deletion, and portability, plus opt-out of sale, targeted advertising, and profiling. Notably has NO consumer appeal right and lower-than-typical thresholds. AG-enforced.",
        "effective_date": "2027-05-01",
        "official_url": "https://legiscan.com/AL/bill/HB351/2026",
        "applicability": "25K+ Alabama consumers OR >25% of gross revenue from the sale of personal data",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "LA",
        "state_name": "Louisiana",
        "law": "LDPA",
        "framework": "LDPA",
        "reference_id": "LDPA-LA",
        "citation": "Louisiana Data Privacy Act, Act 502 / SB 386 (2026) — codification pending",
        "title": "Louisiana Data Privacy Act",
        "summary": "SIGNED 2026-05-29, EFFECTIVE 2027-01-01. VCDPA-model law granting access, correction, deletion, portability, and appeal, plus opt-out of sale, targeted advertising, and profiling. Opt-in consent for sensitive data; honors universal opt-out mechanisms. AG-exclusive enforcement (cure period sunsets 2027-07-31).",
        "effective_date": "2027-01-01",
        "official_url": "https://legiscan.com/LA/bill/SB386/2026",
        "applicability": "$25M+ revenue OR 75K+ consumers OR >50% revenue from selling personal information",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout",
        ],
    },
    {
        "jurisdiction": "VT",
        "state_name": "Vermont",
        "law": "VDPOSA",
        "framework": "VDPOSA",
        "reference_id": "VDPOSA-VT",
        "citation": "Vermont Data Privacy and Online Surveillance Act, Act 145 / S.71 (2026)",
        "title": "Vermont Data Privacy and Online Surveillance Act",
        "summary": "SIGNED 2026-06-16, EFFECTIVE 2028-01-01 (cure period through 2029-06-30). Successor to the 2024 bill vetoed by Gov. Scott. Low applicability threshold (35K consumers), adds an AI/LLM-training disclosure requirement. The private right of action was dropped from the comprehensive framework.",
        "effective_date": "2028-01-01",
        "official_url": "https://legislature.vermont.gov/bill/status/2026/S.71",
        "applicability": "35K+ consumers (low threshold)",
        "requirements": [
            "consumer_rights_access", "consumer_rights_deletion", "consumer_rights_correction",
            "consumer_rights_portability", "consumer_rights_appeal",
            "opt_out_sale_share", "opt_out_targeted_advertising",
            "sensitive_data_consent", "notice_requirement",
            "universal_optout_signal", "ai_profiling_optout", "childrens_data_restrictions",
        ],
    },
]

# Domain mapping for requirement types → repo domain slugs
REQ_DOMAIN_MAP = {
    "consumer_rights_access": "consumer_rights",
    "consumer_rights_deletion": "consumer_rights",
    "consumer_rights_correction": "consumer_rights",
    "consumer_rights_portability": "consumer_rights",
    "consumer_rights_appeal": "consumer_rights",
    "opt_out_sale_share": "data_sharing",
    "opt_out_targeted_advertising": "tracking_cookies",
    "sensitive_data_consent": "sensitive_data",
    "notice_requirement": "other",
    "retention_disclosure": "retention",
    "universal_optout_signal": "tracking_cookies",
    "ai_profiling_optout": "ai_automated_decisions",
    "childrens_data_restrictions": "children_teens",
    "private_right_of_action": "consumer_rights",
}


def _stable_uuid(seed: str) -> str:
    """Deterministic UUID v5 for idempotent upserts."""
    import uuid as _uuid
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, seed))


def try_openstates_url(state_name: str) -> str | None:
    """Try to find the privacy bill URL from OpenStates."""
    if not OPENSTATES_API_KEY:
        return None
    try:
        r = httpx.get(
            f"https://v3.openstates.org/bills?jurisdiction={state_name}"
            f"&q=consumer+data+privacy&apikey={OPENSTATES_API_KEY}&per_page=5",
            timeout=20,
            follow_redirects=True,
        )
        if r.status_code == 200:
            for bill in r.json().get("results", []):
                title = (bill.get("title") or "").lower()
                if any(kw in title for kw in ["privacy", "data protection", "consumer data"]):
                    sources = bill.get("sources", [])
                    if sources:
                        return sources[0].get("url")
                    openstates_url = bill.get("openstates_url")
                    if openstates_url:
                        return openstates_url
    except Exception as exc:
        log.warning("OpenStates lookup for %s failed: %s", state_name, exc)
    return None


def build_obligation_rows(law: dict) -> list[dict]:
    """Build obligation rows for a single state law."""
    rows = []
    for req_type in law["requirements"]:
        oid = _stable_uuid(f"obligation:{law['jurisdiction']}:{law['law']}:{req_type}")
        rows.append({
            "obligation_id": oid,
            "jurisdiction": law["jurisdiction"],
            "law": law["law"],
            "domain": REQ_DOMAIN_MAP.get(req_type, "other"),
            "requirement_type": req_type,
            "applicability": law["applicability"],
            "effective_date": law.get("effective_date"),
        })
    return rows


def build_legal_ref_row(law: dict) -> dict:
    """Build a legal_reference row for a single state law."""
    return {
        "reference_id": law["reference_id"],
        "jurisdiction": f"US-{law['jurisdiction']}",
        "framework": law["framework"],
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": law["citation"],
        "title": law["title"],
        "summary": law["summary"],
        "full_text": None,
        "domain": "consumer_rights",
        "effective_date": law.get("effective_date"),
        "official_url": law["official_url"],
        "source_name": "state_legislature",
        "content_hash": sha256_text(law["citation"]),
        "sme_authored": False,
    }


def main():
    run_id = start_run("state_laws", "full")
    total_obligations = 0
    total_refs = 0

    all_obligation_rows = []
    all_ref_rows = []

    for law in NEW_STATE_LAWS:
        log.info("Processing %s (%s)...", law["law"], law["jurisdiction"])

        # Try OpenStates for a better URL
        os_url = try_openstates_url(law["state_name"])
        if os_url:
            log.info("  OpenStates URL for %s: %s", law["state_name"], os_url)
        time.sleep(0.5)  # Rate limit

        # Build obligation rows
        ob_rows = build_obligation_rows(law)
        all_obligation_rows.extend(ob_rows)
        log.info("  %d obligation rows for %s", len(ob_rows), law["law"])

        # Build legal_reference row
        ref_row = build_legal_ref_row(law)
        all_ref_rows.append(ref_row)

    # Upsert legal_reference first (obligations don't FK to it, but good order)
    if all_ref_rows:
        n = upsert("legal_reference", all_ref_rows, "reference_id")
        total_refs = n
        log.info("legal_reference: upserted %d rows", n)

    # Upsert obligations
    if all_obligation_rows:
        n = upsert("obligation", all_obligation_rows, "obligation_id")
        total_obligations = n
        log.info("obligation: upserted %d rows", n)

    finish_run(run_id, inserted=total_obligations + total_refs, status="ok")

    print(f"\n{'='*60}")
    print(f"  Legal references: {total_refs}")
    print(f"  Obligations:      {total_obligations}")
    print(f"  States added:     {len(NEW_STATE_LAWS)}")
    print(f"  Ingestion run:    {run_id}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
