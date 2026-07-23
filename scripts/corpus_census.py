"""Corpus census — STRICTLY READ-ONLY snapshot of the live corpus.

Produces logs/audits/census-{date}.md from LIVE queries only (Hard Rule 7: no
hardcoded or estimated numbers — every figure comes from a live query). No
INSERT/UPDATE/DELETE/DDL is ever issued; the DB connection is opened read-only. No
secrets, connection strings, or keys appear in the output.

Sections:
  1. Per-table row counts (Prompt-0 list + ingestion layer) with deltas vs the
     previous census file, if one exists.
  2. Organizations per industry; notices-per-organization distribution;
     benchmark-eligible orgs per industry vs the n>=20 Release-1 target and the
     LOW_CONFIDENCE_COHORT_N threshold.
  3. Clause counts per category_v2 (incl. the 'other' percentage).
  4. security_event by entity_type + year; enforcement_record by regulator + year;
     unresolved org matches (NULL organization_id).
  5. ingestion_run health: last run per family, outcome, error summary.
  6. raw-artifacts object counts per family folder (Storage API).

Run:  make census   ·   PYTHONPATH=. python scripts/corpus_census.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "logs" / "audits"
RELEASE1_TARGET_N = 20                                   # normalization band "adjacent" floor (engine.py)

# Prompt-0 corpus tables, then the F02 ingestion/connector layer.
CORE_TABLES = ["organization", "source_record", "privacy_notice", "notice_section",
               "disclosure_clause", "obligation", "enforcement_record", "regulator",
               "litigation_event", "benchmark_membership", "training_label",
               "monitoring_event", "report_snapshot"]
INGEST_TABLES = ["source_registry", "ingestion_run", "parser_version", "source_version",
                 "security_event", "organization_alias", "schema_migrations",
                 "crawl_target", "sic_industry_map", "ftc_topic_domain_map"]


def _low_confidence_cohort_n() -> int:
    """Read LOW_CONFIDENCE_COHORT_N from the single source of truth (scoreBands.ts)."""
    f = ROOT / "web" / "src" / "lib" / "scoreBands.ts"
    if f.exists():
        m = re.search(r"LOW_CONFIDENCE_COHORT_N\s*=\s*(\d+)", f.read_text(encoding="utf-8"))
        if m:
            return int(m.group(1))
    return 10                                            # OD-05 pending default (build_agents_md.py)


def _conn_kwargs():
    spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._conn_kwargs()[0]


def _service_headers():
    spec = importlib.util.spec_from_file_location("_db", ROOT / "app" / "db.py")
    # app.db needs the package importable; use the real import instead
    from app.db import get_service_headers  # noqa: E402
    return get_service_headers()


def _fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


# ── storage: recursive object count per family folder ───────────────

def raw_artifact_counts(supabase_url: str, headers: dict) -> dict[str, int]:
    """Count objects under each top-level family folder of the raw-artifacts bucket
    (Storage list API, recursive). Read-only."""
    bucket = "raw-artifacts"

    def _list(prefix: str) -> list[dict]:
        out, offset = [], 0
        while True:
            r = httpx.post(f"{supabase_url}/storage/v1/object/list/{bucket}",
                           headers={**headers, "Content-Type": "application/json"},
                           json={"prefix": prefix, "limit": 1000, "offset": offset,
                                 "sortBy": {"column": "name", "order": "asc"}}, timeout=60)
            batch = r.json() if r.status_code < 300 else []
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
        return out

    def _count(prefix: str) -> int:
        total = 0
        for entry in _list(prefix):
            name = entry.get("name")
            if not name:
                continue
            # a folder has no id/metadata; an object carries an id + metadata
            if entry.get("id") is None and entry.get("metadata") is None:
                total += _count(f"{prefix}{name}/")
            else:
                total += 1
        return total

    counts = {}
    for entry in _list(""):
        name = entry.get("name")
        if name and entry.get("id") is None and entry.get("metadata") is None:
            counts[name] = _count(f"{name}/")
    return counts


# ── previous-census delta parsing ───────────────────────────────────

def previous_counts(today_name: str) -> tuple[dict[str, int], str | None]:
    if not AUDITS.exists():
        return {}, None
    prev = sorted(p for p in AUDITS.glob("census-*.md") if p.name != today_name)
    if not prev:
        return {}, None
    latest = prev[-1]
    counts = {}
    for line in latest.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`?([a-z_]+)`?\s*\|\s*([\d,]+)\s*\|", line)
        if m:
            counts[m.group(1)] = int(m.group(2).replace(",", ""))
    return counts, latest.name


# ── report builder ───────────────────────────────────────────────────

def build(cur, storage_counts: dict[str, int], today: str, low_conf_n: int) -> str:
    def scalar(sql, args=()):
        cur.execute(sql, args)
        return cur.fetchone()[0]

    def rows(sql, args=()):
        cur.execute(sql, args)
        return cur.fetchall()

    def table_exists(t):
        return scalar("SELECT count(*) FROM information_schema.tables WHERE table_name=%s", (t,)) > 0

    L = [f"# Corpus Census — {today}", "",
         "**Read-only.** Every number below is from a live query (Hard Rule 7). "
         "No writes were issued; no secrets appear in this report.", ""]

    # 1. table counts + deltas
    prev, prev_name = previous_counts(f"census-{today}.md")
    L += ["## 1. Table row counts",
          f"_Deltas vs `{prev_name}`._" if prev_name else "_No previous census found — deltas omitted._",
          "", "| Table | Rows | Δ |", "|---|---:|---:|"]
    for t in CORE_TABLES + INGEST_TABLES:
        if not table_exists(t):
            L.append(f"| {t} | _absent_ | — |")
            continue
        n = scalar(f"SELECT count(*) FROM {t}")
        if t in prev:
            d = n - prev[t]
            delta = "±0" if d == 0 else (f"+{_fmt(d)}" if d > 0 else _fmt(d))
        else:
            delta = "new" if prev_name else "—"
        L.append(f"| {t} | {_fmt(n)} | {delta} |")

    # 2. orgs per industry / notices distribution / benchmark eligibility
    L += ["", "## 2. Organizations, notices & benchmark eligibility", "",
          "**Organizations per industry:**", "", "| Industry | Orgs |", "|---|---:|"]
    for ind, n in rows("SELECT COALESCE(industry,'(null)'), count(*) FROM organization "
                       "GROUP BY industry ORDER BY 2 DESC"):
        L.append(f"| {ind} | {_fmt(n)} |")

    total_orgs = scalar("SELECT count(*) FROM organization")
    with_notice = scalar("SELECT count(DISTINCT organization_id) FROM privacy_notice "
                         "WHERE organization_id IS NOT NULL")
    L += ["", "**Notices per organization (distribution):**", "",
          "| Notices | Orgs |", "|---:|---:|",
          f"| 0 | {_fmt(total_orgs - with_notice)} |"]
    for n_notices, n_orgs in rows(
            "SELECT n, count(*) FROM (SELECT organization_id, count(*) n FROM privacy_notice "
            "WHERE organization_id IS NOT NULL GROUP BY organization_id) s GROUP BY n ORDER BY n"):
        L.append(f"| {n_notices} | {_fmt(n_orgs)} |")

    L += ["", f"**Benchmark-eligible orgs per industry** (eligible = has ≥1 privacy_notice; "
          f"Release-1 target n≥{RELEASE1_TARGET_N}, low-confidence floor "
          f"LOW_CONFIDENCE_COHORT_N={low_conf_n}):", "",
          "| Industry | Eligible | vs target |", "|---|---:|---|"]
    for ind, n in rows(
            "SELECT COALESCE(o.industry,'(null)'), count(DISTINCT o.organization_id) "
            "FROM organization o JOIN privacy_notice p ON p.organization_id=o.organization_id "
            "GROUP BY o.industry ORDER BY 2 DESC"):
        flag = (f"✅ ≥{RELEASE1_TARGET_N} (target met)" if n >= RELEASE1_TARGET_N
                else (f"⚠️ ≥{low_conf_n} (low-confidence only)" if n >= low_conf_n
                      else f"❌ <{low_conf_n} (insufficient)"))
        L.append(f"| {ind} | {_fmt(n)} | {flag} |")

    # 3. clause category_v2 + other %
    cat_rows = rows("SELECT COALESCE(category_v2,'(null/unclassified)'), count(*) "
                    "FROM disclosure_clause GROUP BY category_v2 ORDER BY 2 DESC")
    total_clauses = sum(n for _, n in cat_rows) or 1
    other_n = next((n for c, n in cat_rows if c == "other"), 0)
    L += ["", "## 3. Clause counts per category_v2",
          f"_'other' = {_fmt(other_n)} ({100*other_n/total_clauses:.1f}% of {_fmt(total_clauses)} clauses)._",
          "", "| category_v2 | Clauses | % |", "|---|---:|---:|"]
    for cat, n in cat_rows:
        L.append(f"| {cat} | {_fmt(n)} | {100*n/total_clauses:.1f}% |")

    # 4. security_event / enforcement_record breakdowns + unresolved
    L += ["", "## 4. External signals & entity resolution", "",
          "**security_event by entity_type:**", "", "| entity_type | Count |", "|---|---:|"]
    for et, n in rows("SELECT COALESCE(entity_type,'(null)'), count(*) FROM security_event "
                      "GROUP BY entity_type ORDER BY 2 DESC"):
        L.append(f"| {et} | {_fmt(n)} |")
    L += ["", "**security_event by year (submission_date):**", "", "| Year | Count |", "|---|---:|"]
    for yr, n in rows("SELECT COALESCE(to_char(submission_date,'YYYY'),'(null)'), count(*) "
                      "FROM security_event GROUP BY 1 ORDER BY 1"):
        L.append(f"| {yr} | {_fmt(n)} |")

    L += ["", "**enforcement_record by regulator:**", "", "| Regulator | Count |", "|---|---:|"]
    for reg, n in rows("SELECT COALESCE(regulator_id,'(null)'), count(*) FROM enforcement_record "
                       "GROUP BY regulator_id ORDER BY 2 DESC"):
        L.append(f"| {reg} | {_fmt(n)} |")
    L += ["", "**enforcement_record by year (action_date):**", "", "| Year | Count |", "|---|---:|"]
    for yr, n in rows("SELECT COALESCE(to_char(action_date,'YYYY'),'(null)'), count(*) "
                      "FROM enforcement_record GROUP BY 1 ORDER BY 1"):
        L.append(f"| {yr} | {_fmt(n)} |")

    se_unres = scalar("SELECT count(*) FROM security_event WHERE organization_id IS NULL")
    se_total = scalar("SELECT count(*) FROM security_event")
    en_unres = scalar("SELECT count(*) FROM enforcement_record WHERE organization_id IS NULL")
    en_total = scalar("SELECT count(*) FROM enforcement_record")
    L += ["", "**Unresolved org matches (NULL organization_id):**", "",
          f"- security_event: {_fmt(se_unres)} / {_fmt(se_total)} unresolved",
          f"- enforcement_record: {_fmt(en_unres)} / {_fmt(en_total)} unresolved"]

    # 5. ingestion_run health
    L += ["", "## 5. ingestion_run health (last run per family)", "",
          "| Family | Outcome | Finished | Error summary |", "|---|---|---|---|"]
    for fam, outcome, status, fin, err in rows(
            "SELECT DISTINCT ON (source_name) source_name, outcome, status, finished_at, error_summary "
            "FROM ingestion_run ORDER BY source_name, finished_at DESC NULLS LAST"):
        fin_s = fin.strftime("%Y-%m-%d %H:%M") if fin else "—"
        err_s = (err or "").replace("|", "/")[:80] or "—"
        L.append(f"| {fam} | {outcome or status or '—'} | {fin_s} | {err_s} |")

    # 6. raw-artifacts objects per family folder
    L += ["", "## 6. raw-artifacts objects per family folder", "", "| Folder | Objects |", "|---|---:|"]
    if storage_counts:
        for folder in sorted(storage_counts):
            L.append(f"| {folder} | {_fmt(storage_counts[folder])} |")
    else:
        L.append("| _(storage list unavailable)_ | — |")

    L += ["", f"---", f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · read-only._"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    import psycopg
    from app.config import settings

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        storage = raw_artifact_counts(settings.supabase_url, _service_headers())
    except Exception as e:  # noqa: BLE001 — storage optional; DB census still emits
        print(f"warning: raw-artifacts listing failed ({type(e).__name__}); folder counts omitted",
              file=sys.stderr)
        storage = {}

    kw = _conn_kwargs()
    with psycopg.connect(**kw) as conn:
        conn.read_only = True                            # hard read-only: no writes possible
        with conn.cursor() as cur:
            report = build(cur, storage, today, _low_confidence_cohort_n())

    AUDITS.mkdir(parents=True, exist_ok=True)
    out = AUDITS / f"census-{today}.md"
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
