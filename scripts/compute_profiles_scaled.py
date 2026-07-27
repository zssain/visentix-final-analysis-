"""Scalable, targeted Organization Intelligence Profiler (VICBNF 7-dimension).

The original scripts/compute_profiles.py was written for the 30-org era: it pulls
EVERY clause (600k+) via deep OFFSET pagination into memory — infeasible now, and it
hits PostgREST statement timeouts. This version:

  • scopes to a bounded set of orgs (by --industry and/or --fresh-only) and does the
    clause→category aggregation SERVER-SIDE (one GROUP BY over just those orgs' clauses,
    via psycopg) — no full-corpus scan;
  • never fabricates a dimension — an org with no clauses is skipped, not defaulted;
  • writes canonical industry_id + tier labels (columns the old script left NULL);
  • inserts a NEW versioned profile row, never overwriting (Rule 4 / lineage).

Deterministic — no model calls. Reuses app.services.profiling.profile.compute_profile.

Usage:
    PYTHONPATH=. python scripts/compute_profiles_scaled.py --fresh-only          # orgs with a fresh open_web notice
    PYTHONPATH=. python scripts/compute_profiles_scaled.py --industry retail healthcare fintech --skip-existing
    PYTHONPATH=. python scripts/compute_profiles_scaled.py --fresh-only --dry-run
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.services.profiling.profile import OrgData, compute_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compute_profiles_scaled")

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

# Canonical 10-industry taxonomy (config/org_profile_weights.json) → industry_id.
_TAX = json.loads((ROOT / "config" / "org_profile_weights.json").read_text())["industry_taxonomy"]


def _industry_id(industry: str | None) -> str:
    return (_TAX.get((industry or "").lower().replace(" ", "_")) or {}).get("industry_id", "IND-00")


def main() -> int:
    import psycopg

    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", nargs="*", default=None, help="filter to these organization.industry values")
    ap.add_argument("--fresh-only", action="store_true", help="only orgs with a notice_type='open_web' (fresh crawl) notice")
    ap.add_argument("--skip-existing", action="store_true", help="skip orgs that already have a profile")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    kw = _ar._conn_kwargs()[0]
    with psycopg.connect(**kw) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            # 1. target org set (bounded)
            where = ["EXISTS (SELECT 1 FROM privacy_notice pn WHERE pn.organization_id = o.organization_id)"]
            params: list = []
            if args.fresh_only:
                where.append("EXISTS (SELECT 1 FROM privacy_notice pn2 WHERE pn2.organization_id = o.organization_id AND pn2.notice_type='open_web')")
            if args.industry:
                where.append("o.industry = ANY(%s)")
                params.append(args.industry)
            if args.skip_existing:
                where.append("NOT EXISTS (SELECT 1 FROM organization_intelligence_profile p WHERE p.organization_id = o.organization_id)")
            sql = ("SELECT o.organization_id, o.name, o.industry, o.size, o.geography, o.public_private "
                   "FROM organization o WHERE " + " AND ".join(where) + " ORDER BY o.organization_id")
            if args.limit:
                sql += f" LIMIT {int(args.limit)}"
            cur.execute(sql, params)
            orgs = cur.fetchall()
            org_ids = [r[0] for r in orgs]
            log.info("target orgs: %d", len(org_ids))
            if not org_ids:
                log.info("nothing to profile"); return 0

            # 2. per-org clause-category histogram, SERVER-SIDE GROUP BY, scoped to the org set
            cur.execute(
                "SELECT o.organization_id, dc.category, count(*) "
                "FROM organization o "
                "JOIN privacy_notice pn ON pn.organization_id = o.organization_id "
                "JOIN notice_section ns ON ns.notice_id = pn.notice_id "
                "JOIN disclosure_clause dc ON dc.section_id = ns.section_id "
                "WHERE o.organization_id = ANY(%s) "
                "GROUP BY o.organization_id, dc.category", (org_ids,))
            hist: dict[str, Counter] = {}
            for oid, cat, n in cur.fetchall():
                hist.setdefault(oid, Counter())[cat or "other"] += n

            # 3. enforcement proxy (jurisdiction-level; same for all US orgs) + regulator weights
            cur.execute("SELECT regulator_id, penalty_usd FROM enforcement_record")
            enf = cur.fetchall()
            total_enf = len(enf)
            total_penalty = sum((e[1] or 0) for e in enf)
            all_regs = [e[0] for e in enf if e[0]]
            cur.execute("SELECT regulator_id, enforcement_frequency_weight FROM regulator")
            reg_weights = {r[0]: r[1] for r in cur.fetchall()}

            # 4. compute + insert
            now = datetime.now(timezone.utc)
            profiled = skipped = 0
            for oid, name, industry, size, geography, pubpriv in orgs:
                cats = hist.get(oid)
                if not cats:
                    skipped += 1
                    continue  # never fabricate a profile for an org with no clauses
                data = OrgData(
                    organization_id=oid, name=name, industry=industry or "unknown",
                    size=size or "large", geography=geography or "US", public_private=pubpriv,
                    clause_categories=cats, total_clauses=sum(cats.values()), has_notice=True,
                    enforcement_count=total_enf, total_penalty_usd=total_penalty,
                    enforcement_regulators=all_regs, regulator_weights=reg_weights,
                )
                p = compute_profile(data)
                cur.execute("SELECT COALESCE(max(profile_version),0)+1 FROM organization_intelligence_profile WHERE organization_id=%s", (oid,))
                version = cur.fetchone()[0]
                if args.dry_run:
                    log.info("[DRY] %s (%s) RSS=%.1f PGMS=%.1f OSI=%.1f DSI=%.1f EHP=%.1f AIGMS=%.1f VCI=%.3f v%d",
                             name, industry, p.rss, p.pgms, p.osi, p.dsi, p.ehp, p.aigms, p.confidence_score, version)
                else:
                    cur.execute(
                        "INSERT INTO organization_intelligence_profile "
                        "(organization_id, ic, rss, pgms, osi, dsi, ehp, aigms, profile_version, confidence_score, "
                        " generated_at, industry_id, sub_industry, rss_tier, pgms_tier, osi_tier, dsi_tier, ehp_tier, aigms_tier) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (oid, hash(p.ic) % 100, p.rss, p.pgms, p.osi, p.dsi, p.ehp, p.aigms, version, p.confidence_score,
                         now, _industry_id(industry), p.ic,
                         p.tiers.get("rss"), p.tiers.get("pgms"), p.tiers.get("osi"),
                         p.tiers.get("dsi"), p.tiers.get("ehp"), p.tiers.get("aigms")))
                profiled += 1
            if not args.dry_run:
                conn.commit()
            log.info("=== profiled %d, skipped %d (no clauses) ===", profiled, skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
