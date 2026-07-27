"""Princeton-Leuven curated privacy-policy corpus connector (family `princeton_leuven`).

BATCH importer over LOCAL per-sector CSVs (columns: domain, category, last_updated,
policy_text) produced offline by the privacy-policy-sector-extract project, placed at
`PRINCETON_EXTRACT_DIR`.

Per row:
- `source_record` (source_type='dataset', tier 2) capturing dataset name + snapshot id
  (= last_updated, e.g. "2019B") and TRUTHFUL freshness — these snapshots end ~2019,
  so `freshness_weight`/`effective_date` are set old, letting downstream CQS gating
  exclude them from ACTIVE benchmark populations (this importer writes NO
  `benchmark_membership` rows — cohort building stays with the F03 job).
- a `privacy_notice` linked to an organization resolved via `organization_alias`
  (domain). No match → a BENCHMARK-ONLY organization (tenant_id NULL, name=domain,
  origin='princeton_leuven') + a domain alias.
- the notice text is decomposed + classified through the EXISTING pipeline function
  `intake.decompose.decompose()` (the same code path customer intake uses); the
  resulting sections/clauses are persisted with the same payload shape.

Dedupe + idempotency: the framework skips any row whose (domain, policy_text sha256)
already has a source_record — so duplicate texts for a domain are skipped and a
re-load of the same snapshot adds ZERO new source_records.

⚠️ LICENSING: see README.md in this folder — research-use licensing must be verified
before any commercial benchmark/publication use (open decision, expert/legal).
"""
from __future__ import annotations

import csv
import hashlib
import logging
import re
import sys
from datetime import date
from pathlib import Path

# Real privacy-policy fields can exceed Python's default 128 KB CSV field limit
# (the Princeton retail export has multi-hundred-KB policy_text cells). Raise it to
# the platform max so no row is dropped mid-parse.
_max = sys.maxsize
while True:
    try:
        csv.field_size_limit(_max)
        break
    except OverflowError:
        _max = int(_max // 10)

from app.config import settings
from app.services.ingestion.base import Connector, RawItem
from app.services.ingestion.connectors.edgar import normalize_domain, slugify
from app.services.intake.classify_v2 import KEYWORD_FALLBACK_VERSION
from app.services.intake.decompose import decompose

log = logging.getLogger(__name__)

DATASET_NAME = "Princeton-Leuven Longitudinal Privacy-Policy Corpus"
REQUIRED_COLUMNS = {"domain", "category", "last_updated", "policy_text"}
# recency window (years) over which freshness decays to 0 — a 2019 snapshot in 2026
# lands at 0.0, so CQS gating excludes it from active benchmarks.
_FRESHNESS_WINDOW_YEARS = 5.0


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def snapshot_year(snapshot: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", snapshot or "")
    return int(m.group(0)) if m else None


def snapshot_date(snapshot: str) -> str | None:
    """Approximate effective date from a snapshot id like '2019B' (A=H1, B=H2)."""
    yr = snapshot_year(snapshot)
    if yr is None:
        return None
    half = "B" if (snapshot or "").strip().upper().endswith("B") else "A"
    return f"{yr}-07-01" if half == "B" else f"{yr}-01-01"


def freshness_weight(snapshot: str, today: date | None = None) -> float:
    """Truthful freshness in [0,1]: decays linearly to 0 over the recency window."""
    yr = snapshot_year(snapshot)
    if yr is None:
        return 0.0
    today = today or date.today()
    age = (today.year - yr) + (today.month - 7) / 12.0
    return round(max(0.0, min(1.0, 1.0 - age / _FRESHNESS_WINDOW_YEARS)), 4)


class PrincetonWriter:
    """DB side-effects for the Princeton import. Tests inject a fake with the same
    surface (resolve_or_create_org / create_notice / persist_notice_body)."""

    def __init__(self):
        from app.config import settings as _s
        self._url = _s.supabase_url

    def _h(self, **extra):
        from app.db import get_service_headers
        return {**get_service_headers(), **extra}

    def _rest(self, p):
        return f"{self._url}/rest/v1/{p}"

    def resolve_or_create_org(self, domain: str, sector: str, source_id: str) -> tuple[str, bool]:
        import httpx
        # 1) existing org via domain alias
        r = httpx.get(self._rest(
            f'organization_alias?select=organization_id&alias_type=eq.domain&value=eq."{domain}"&limit=1'),
            headers=self._h(), timeout=30)
        rows = r.json() if r.status_code < 300 else []
        if rows:
            return rows[0]["organization_id"], False
        # 2) existing org whose organization.domain matches
        r = httpx.get(self._rest(
            f'organization?select=organization_id&or=(domain.eq."{domain}",domain.eq."www.{domain}")&limit=1'),
            headers=self._h(), timeout=30)
        rows = r.json() if r.status_code < 300 else []
        if rows:
            return rows[0]["organization_id"], False
        # 3) create a BENCHMARK-ONLY org (tenant_id NULL, origin flag)
        base = slugify(domain)
        for attempt in range(4):
            payload = {"name": domain, "slug": base if attempt == 0 else f"{base}-pl-{attempt}",
                       "domain": domain, "industry": sector or "unknown", "entity_type": "peer",
                       "tenant_id": None, "origin": "princeton_leuven"}
            resp = httpx.post(self._rest("organization"),
                              headers=self._h(**{"Content-Type": "application/json",
                                                 "Prefer": "return=representation"}),
                              json=payload, timeout=30)
            if resp.status_code < 300:
                org_id = resp.json()[0]["organization_id"]
                self._upsert_domain_alias(org_id, domain, source_id)
                return org_id, True
            if resp.status_code == 409 and "slug" in (resp.text or ""):
                continue
            raise RuntimeError(f"organization insert failed: HTTP {resp.status_code}")
        raise RuntimeError("organization insert failed: slug collisions exhausted")

    def _upsert_domain_alias(self, org_id, domain, source_id):
        import httpx
        httpx.post(self._rest("organization_alias?on_conflict=alias_type,value"),
                   headers=self._h(**{"Content-Type": "application/json",
                                      "Prefer": "resolution=ignore-duplicates,return=minimal"}),
                   json=[{"organization_id": org_id, "alias_type": "domain", "value": domain,
                          "match_confidence": 1.0, "source_record_id": source_id}], timeout=30)

    def create_notice(self, org_id: str, rec: dict) -> str:
        import httpx
        from uuid import uuid4
        notice = rec["notice"]
        cats = {c.category for c in notice.clauses}
        mean_conf = (sum(c.nlp_confidence for c in notice.clauses) / len(notice.clauses)
                     if notice.clauses else 0.0)
        notice_id = str(uuid4())
        payload = {
            "notice_id": notice_id, "organization_id": org_id,
            "notice_type": "dataset",                      # curated-corpus notice, not a live assessment
            "url": rec["domain"], "effective_date": rec["effective_date"],  # TRUTHFUL: ~2019
            "retrieval_date": str(date.today()), "content_hash": rec["content_hash"],
            "version_id": 0, "jurisdiction_scope": ["US"], "storage_path": rec.get("storage_path", ""),
            "extraction_confidence": round(mean_conf, 4),
            "ai_disclosure_presence": "ai_automated_decisions" in cats,
            "tracking_disclosure_presence": "tracking_cookies" in cats,
            "consumer_rights_presence": "consumer_rights" in cats,
            "retention_disclosure_presence": "retention" in cats,
            "cross_border_indicator": "cross_border" in cats,
            "sensitive_data_indicator": "sensitive_data" in cats,
        }
        r = httpx.post(self._rest("privacy_notice"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=payload, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"privacy_notice insert failed: HTTP {r.status_code}")
        return notice_id

    def persist_notice_body(self, notice_id: str, notice) -> None:
        """Persist notice_section + disclosure_clause with the SAME payload shape as
        the intake router (assessments.py §5b/§5c)."""
        import httpx
        section_rows = [{"section_id": s.section_id, "notice_id": notice_id, "title": s.title,
                         "section_type": s.section_type, "sequence": s.sequence,
                         "extracted_text": s.text[:10000]} for s in notice.sections]
        if section_rows:
            httpx.post(self._rest("notice_section"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=section_rows, timeout=60)
        # Set category_v2 at ingest from decompose's keyword label so a bulk-imported
        # clause is NEVER left with a NULL category_v2 (keeps the intake invariant); the
        # LLM reclassifier can still upgrade any it wants later.
        clause_rows = [{"clause_id": c.clause_id, "section_id": c.section_id,
                        "raw_text": c.raw_text[:5000], "normalized_text": c.normalized_text[:5000],
                        "category": c.category, "ambiguity_score": c.ambiguity_score,
                        "readability_score": c.readability_score, "nlp_confidence": c.nlp_confidence,
                        "domain_id": c.domain_id or None, "clause_type": c.clause_type or None,
                        "transparency_score": c.transparency_score,
                        "category_v2": c.category or "other",
                        "nlp_confidence_v2": c.nlp_confidence,
                        "classifier_version": KEYWORD_FALLBACK_VERSION} for c in notice.clauses]
        if clause_rows:
            httpx.post(self._rest("disclosure_clause"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=clause_rows, timeout=60)


class PrincetonConnector(Connector):
    family = "princeton_leuven"
    source_type = "dataset"
    parser_version = "princeton-leuven-csv-v1"
    parser_description = "Princeton-Leuven privacy-policy CSVs → source_record(dataset) + privacy_notice via intake.decompose"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, *, limit: int | None = None,
                 extract_dir: str | None = None, rows: list[dict] | None = None,
                 writer: PrincetonWriter | None = None):
        cfg = (registry_row or {}).get("config") or {}
        self._dir = Path(extract_dir or cfg.get("extract_dir") or settings.princeton_extract_dir or "")
        self._limit = limit
        self._rows = rows                                  # test-injectable (skip disk read)
        self._writer = writer
        self._meta: dict[str, dict] = {}
        # metrics
        self._notices = 0
        self._orgs_created = 0
        self._orgs_matched = 0
        self._clauses = 0
        self._sector_counts: dict[str, int] = {}
        self._confidences: list[float] = []
        self._malformed = 0

    def _w(self) -> PrincetonWriter:
        if self._writer is None:
            self._writer = PrincetonWriter()
        return self._writer

    # ── read the per-sector CSVs ─────────────────────────────────────
    def _read_rows(self) -> list[dict]:
        if self._rows is not None:
            return self._rows
        out: list[dict] = []
        if not self._dir or not self._dir.exists():
            raise FileNotFoundError(
                f"PRINCETON_EXTRACT_DIR not found: {self._dir!r}. Provide the per-sector CSVs "
                f"(domain,category,last_updated,policy_text).")
        per_sector: dict[str, list[dict]] = {}
        for csv_path in sorted(self._dir.glob("*.csv")):
            with csv_path.open(newline="", encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                if not REQUIRED_COLUMNS.issubset({(c or "").strip() for c in (reader.fieldnames or [])}):
                    log.warning("skipping %s: missing required columns %s", csv_path.name, REQUIRED_COLUMNS)
                    continue
                sector = csv_path.stem.lower()   # the per-file name IS the sector
                bucket = per_sector.setdefault(sector, [])
                for row in reader:
                    r = {k: (row.get(k) or "").strip() if k != "policy_text" else (row.get(k) or "")
                         for k in REQUIRED_COLUMNS}
                    r["sector"] = sector          # `category` column keeps the finer compound tags
                    bucket.append(r)
        # Round-robin interleave across sectors so a --limit pilot samples ALL sectors,
        # not just the alphabetically-first file.
        buckets = list(per_sector.values())
        for i in range(max((len(b) for b in buckets), default=0)):
            for b in buckets:
                if i < len(b):
                    out.append(b[i])
        return out

    def fetch(self) -> list[RawItem]:
        rows = self._read_rows()
        items: list[RawItem] = []
        seen: set[str] = set()
        for row in rows:
            if self._limit is not None and len(items) >= self._limit:
                break
            domain = normalize_domain(row.get("domain"))
            text = row.get("policy_text") or ""
            if not domain or not text.strip():
                self._malformed += 1                       # never silently dropped: counted + warned
                continue
            sha = _sha(text)
            nk = f"{domain}::{sha}"                         # dedupe key: (domain, policy_text sha256)
            if nk in seen:
                continue
            seen.add(nk)
            snap = row.get("last_updated") or ""
            # sector = per-file name (from disk read); tests inject `category` directly.
            sector = row.get("sector") or row.get("category") or ""
            dataset_category = row.get("category") or ""       # dataset's finer compound tags
            self._meta[nk] = {"domain": domain, "sector": sector, "snapshot": snap,
                              "content_hash": sha, "effective_date": snapshot_date(snap)}
            items.append(RawItem(
                data=text.encode("utf-8"), content_type="text/plain",
                source_url=domain, natural_key=nk,
                title=f"{DATASET_NAME} — {sector} [{snap}]", jurisdiction="US",
                source_record_extra={
                    "notes": f"origin=princeton_leuven; dataset={DATASET_NAME}; "
                             f"snapshot={snap}; sector={sector}; category={dataset_category}; "
                             f"reliability_tier=2",
                    "effective_date": snapshot_date(snap), "update_date": snapshot_date(snap),
                    "freshness_weight": freshness_weight(snap),   # TRUTHFUL (≈0 for 2019)
                    "completeness_weight": 1.0, "source_reliability_score": None,
                }))
        log.info("princeton fetch: %d notices (%d malformed skipped)", len(items), self._malformed)
        return items

    def parse(self, item: RawItem) -> list[dict]:
        meta = self._meta[item.natural_key]
        # SAME pipeline function the intake path uses — decomposition + classification.
        notice = decompose(item.data.decode("utf-8", "replace"))
        return [{**meta, "notice": notice, "storage_path": ""}]

    def upsert(self, records: list[dict]) -> None:
        w = self._w()
        for rec in records:
            self._notices += 1
            self._sector_counts[rec["sector"]] = self._sector_counts.get(rec["sector"], 0) + 1
            org_id, created = w.resolve_or_create_org(rec["domain"], rec["sector"], rec["source_record_id"])
            if created:
                self._orgs_created += 1
            else:
                self._orgs_matched += 1
            notice_id = w.create_notice(org_id, rec)
            w.persist_notice_body(notice_id, rec["notice"])
            self._clauses += len(rec["notice"].clauses)
            self._confidences.extend(c.nlp_confidence for c in rec["notice"].clauses)

    def record_counts(self) -> dict:
        return {"seen": self._notices, "new": self._notices, "changed": 0, "skipped": 0}

    def run_warnings(self) -> list[str]:
        return [f"{self._malformed} malformed rows skipped (missing domain/text)"] if self._malformed else []

    @property
    def metrics(self) -> dict:
        return {"notices": self._notices, "orgs_created": self._orgs_created,
                "orgs_matched": self._orgs_matched, "clauses": self._clauses,
                "sector_counts": dict(self._sector_counts),
                "confidence_distribution": _distribution(self._confidences)}


def _distribution(confs: list[float]) -> dict:
    if not confs:
        return {}
    buckets = {"<0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, ">=0.9": 0}
    for c in confs:
        if c < 0.5:
            buckets["<0.5"] += 1
        elif c < 0.7:
            buckets["0.5-0.7"] += 1
        elif c < 0.9:
            buckets["0.7-0.9"] += 1
        else:
            buckets[">=0.9"] += 1
    return buckets
