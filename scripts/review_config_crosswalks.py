"""Phase-1 expert-gated config review (attributed ai_reviewed, never impersonating
the human SME). Idempotent; reproducible record of the review decisions.

WHAT IT DOES
1. sic_industry_map — reviews each DRAFT SIC→industry row against the CANONICAL
   10-industry taxonomy (config/org_profile_weights.json / intelligence-logic §2).
   The draft rows carried industry_id codes from an obsolete 6-industry numbering
   that COLLIDES with the canonical scheme (e.g. draft IND-03 Healthcare vs canonical
   IND-04 Healthcare). Corrects each code to canonical and sets mapped_by='ai_reviewed'.
   The two 'Entertainment & Media' rows have NO canonical equivalent (their IND-06
   collides with canonical 'Insurance') → left mapped_by='draft', flagged as an open
   question. Nothing here is silently applied to organization.industry_id.

2. ftc_topic_domain_map — populates the empty scaffold by crosswalking the FTC topic
   tags actually present on enforcement_record.issue_tags to the eight Visentix
   disclosure domains (CR/DC/SH/RT/AI/SEC/TRK/XB, intelligence-logic §4). Descriptive
   mappings only. Tags that are sector/program/statute/harm labels (not a single
   disclosure domain) are recorded with domain=NULL and a note — honest, not forced.

Run: PYTHONPATH=. .venv/bin/python scripts/review_config_crosswalks.py
"""
from __future__ import annotations

import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

REVIEWER = "Claude (ai_reviewed)"

# ── 1. sic_industry_map corrections → canonical 10-industry taxonomy ──
# map_id -> (canonical_industry_id, canonical_industry_name, note)
SIC_CORRECTIONS = {
    "sic:5200-5999": ("IND-01", "Retail & Consumer",
                      "confirmed: SIC 52-59 retail → canonical IND-01 (retail). Unchanged."),
    "sic:7370-7379": ("IND-07", "Technology & SaaS",
                      "corrected IND-02→IND-07: SIC 7370-7379 software/data-processing maps to canonical technology/saas (IND-07); draft IND-02 was the obsolete Software&SaaS code (collides with canonical hospitality)."),
    "sic:2833-2836": ("IND-04", "Healthcare & Life Sciences",
                      "corrected IND-03→IND-04: pharmaceutical/biological → canonical healthcare (IND-04); draft IND-03 collides with canonical transportation/logistics."),
    "sic:3826-3826": ("IND-04", "Healthcare & Life Sciences",
                      "corrected IND-03→IND-04: laboratory analytical instruments → canonical healthcare (IND-04)."),
    "sic:3841-3845": ("IND-04", "Healthcare & Life Sciences",
                      "corrected IND-03→IND-04: surgical/medical/electromedical instruments → canonical healthcare (IND-04)."),
    "sic:8000-8099": ("IND-04", "Healthcare & Life Sciences",
                      "corrected IND-03→IND-04: SIC 80 health services → canonical healthcare (IND-04)."),
    "sic:6000-6199": ("IND-05", "Financial Services",
                      "corrected IND-04→IND-05: credit institutions → canonical financial_services (IND-05); draft IND-04 collides with canonical healthcare."),
    "sic:6200-6299": ("IND-05", "Financial Services",
                      "corrected IND-04→IND-05: security & commodity brokers → canonical financial_services (IND-05)."),
    "sic:6300-6411": ("IND-06", "Insurance",
                      "corrected IND-04→IND-06 AND reclassified name: SIC 6300-6411 is insurance carriers/agents → canonical insurance (IND-06), a distinct industry from financial_services in the canonical taxonomy."),
    "sic:6700-6799": ("IND-05", "Financial Services",
                      "corrected IND-04→IND-05: holding & investment offices → canonical financial_services (IND-05)."),
    "sic:8200-8299": ("IND-09", "Education",
                      "corrected IND-05→IND-09: educational services → canonical education (IND-09); draft IND-05 collides with canonical financial_services."),
}
# Rows with NO canonical equivalent — NOT approved, left draft, flagged.
SIC_NO_CANONICAL = {
    "sic:2700-2799": "NOT approved (OD-09): 'Entertainment & Media' (SIC 2700-2799 publishing) has no equivalent in the canonical 10-industry taxonomy; draft IND-06 collides with canonical 'Insurance'. Left as draft pending an expert decision to add a media industry or remap.",
    "sic:7800-7999": "NOT approved (OD-09): 'Entertainment & Media' (SIC 7800-7999 motion pictures/amusement) has no equivalent in the canonical 10-industry taxonomy; draft IND-06 collides with canonical 'Insurance'. Left as draft pending an expert decision.",
}

# ── 2. ftc_topic_domain_map — FTC topic tag → Visentix domain (or NULL) ──
# (domain, note). domain=None means reviewed → no single disclosure domain.
FTC_MAP = {
    "ai_automated_decisions": ("AI", "FTC tag → AI (automated decisions / profiling), intelligence-logic §4."),
    "consumer_rights":        ("CR", "FTC tag → CR (consumer rights)."),
    "data_sharing":           ("SH", "FTC tag → SH (sharing)."),
    "retention":              ("RT", "FTC tag → RT (retention)."),
    "tracking_cookies":       ("TRK", "FTC tag → TRK (tracking/cookies)."),
    "sensitive_data":         ("DC", "FTC tag → DC (data collection: sensitive PI categories)."),
    "children_teens":         ("DC", "FTC tag → DC (data collection: children, per §4 DC scope)."),
    "Children's Privacy":     ("DC", "FTC topic → DC (children's PI collection)."),
    "Data Security":          ("SEC", "FTC topic → SEC (safeguards / data security)."),
    "Privacy and Security":   ("SEC", "FTC topic → SEC (safeguards / security disclosures)."),
    "Health Privacy":         ("DC", "FTC topic → DC (health data = sensitive PI category)."),
    "other":                     (None, "aggregation bucket; no single disclosure domain."),
    "Consumer Protection":       (None, "FTC bureau/program label, not a disclosure domain."),
    "Bureau of Consumer Protection": (None, "FTC organizational unit, not a disclosure domain."),
    "Consumer Privacy":          (None, "umbrella program label spanning multiple domains; no single domain."),
    "Fair Credit Reporting Act (FCRA)": (None, "statute citation, not a single disclosure domain."),
    "Credit Reporting":          (None, "spans consumer-rights + sharing; no single disclosure domain."),
    "Social Media":              (None, "sector/context tag, not a disclosure domain."),
    "Tech":                      (None, "sector tag, not a disclosure domain."),
    "Health":                    (None, "sector tag; see 'Health Privacy'→DC for the disclosure-domain mapping."),
    "deceptive/misleading conduct": (None, "conduct type, not a disclosure domain."),
    "Advertising and Marketing Basics": (None, "FTC program label; advertising spans TRK+SH — no single domain."),
    "Online Advertising and Marketing": (None, "spans TRK+SH; no single disclosure domain."),
    "housing":                   (None, "sector/context tag, not a disclosure domain."),
    "Identity Theft":            (None, "harm type, not a disclosure domain."),
}


def slug(topic: str) -> str:
    return "ftc:" + re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def main() -> int:
    import psycopg
    kw, label = _ar._conn_kwargs()
    print(f"connecting via {label}")
    now = datetime.now(timezone.utc)
    with psycopg.connect(autocommit=False, **kw) as conn:
        with conn.cursor() as cur:
            # 1. sic corrections
            for map_id, (ind_id, ind_name, note) in SIC_CORRECTIONS.items():
                cur.execute(
                    "UPDATE sic_industry_map SET industry_id=%s, industry_name=%s, "
                    "mapped_by='ai_reviewed', reviewed_by=%s, reviewed_at=%s, "
                    "notes = COALESCE(notes,'') || %s WHERE map_id=%s",
                    (ind_id, ind_name, REVIEWER, now, f" · 2026-07-27 ai_reviewed: {note}", map_id))
            for map_id, note in SIC_NO_CANONICAL.items():
                cur.execute(
                    "UPDATE sic_industry_map SET reviewed_by=%s, reviewed_at=%s, "
                    "notes = COALESCE(notes,'') || %s WHERE map_id=%s",
                    (REVIEWER, now, f" · 2026-07-27 ai_reviewed: {note}", map_id))
            # 2. ftc map upserts
            for topic, (domain, note) in FTC_MAP.items():
                cur.execute(
                    "INSERT INTO ftc_topic_domain_map (map_id, ftc_topic, domain, mapped_by, notes, reviewed_by, reviewed_at) "
                    "VALUES (%s,%s,%s,'ai_reviewed',%s,%s,%s) "
                    "ON CONFLICT (map_id) DO UPDATE SET domain=EXCLUDED.domain, "
                    "mapped_by='ai_reviewed', notes=EXCLUDED.notes, reviewed_by=EXCLUDED.reviewed_by, "
                    "reviewed_at=EXCLUDED.reviewed_at",
                    (slug(topic), topic, domain, note, REVIEWER, now))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT mapped_by, count(*) FROM sic_industry_map GROUP BY 1 ORDER BY 1")
            print("sic_industry_map by mapped_by:", cur.fetchall())
            cur.execute("SELECT mapped_by, count(*) FROM ftc_topic_domain_map GROUP BY 1 ORDER BY 1")
            print("ftc_topic_domain_map by mapped_by:", cur.fetchall())
            cur.execute("SELECT count(*) FROM ftc_topic_domain_map WHERE domain IS NOT NULL")
            print("ftc rows with a domain:", cur.fetchone()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
