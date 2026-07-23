"""SEC EDGAR bulk-import connector (family `sec_edgar`).

A BATCH IMPORTER, not a crawler. The full EDGAR bulk download already lives on
disk at `EDGAR_BULK_PATH` (submissions/ + companyfacts/). This connector reads
LOCAL files only. The single permitted network call is fetching
`company_tickers.json` from sec.gov IFF it is missing from the bulk (the roster of
ticker-bearing operating companies); it is then cached into the bulk dir.

What it does, per company:
  - Reads the local `submissions/CIK##########.json` metadata.
  - Filters to the mapped industries (SIC -> industry via config/sic_industry_map.json).
  - Creates or ADDITIVELY enriches one `organization` row — it NEVER overwrites an
    existing non-null field; it writes only into null fields.
  - Writes `organization_alias` rows (cik / ticker / legal_name / domain) with
    match_confidence 1.0 (authoritative), idempotent on the DB's UNIQUE(alias_type,value).

Profiling boundary (owned by the deterministic profiler — NOT this connector):
  - The SIC->industry map is a DRAFT (mapped_by='draft'). This importer does NOT
    write industry_id onto organizations; it only records the draft suggestion as an
    INPUT in size_metadata for a later expert-approval step. New orgs get
    industry='unknown', industry_id=NULL.
  - It records size/sophistication INPUTS only (filer category, SIC, employee count
    / revenue if present in the bulk metadata). It computes NO profile scores and
    touches nothing in organization_intelligence_profile.

Security posture (AGENTS.md §3): local JSON is untrusted data — json.loads only,
never eval/exec. Logs carry counts/keys, never full record text or secrets.
"""
from __future__ import annotations

import abc
import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Connector, RawItem

log = logging.getLogger(__name__)

# SEC's CDN requires a UA carrying a real name + contact email (generic UAs get 403).
_UA = "Visentix Research sales@teclusion.ai"
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_ROOT = Path(__file__).resolve().parents[4]
_SIC_MAP_FILE = _ROOT / "config" / "sic_industry_map.json"

# Only these columns are ever sent to the `organization` table (guards against
# leaking the framework's lineage keys, mirroring the HHS connector's pattern).
ORG_COLUMNS = {
    "name", "slug", "domain", "industry", "industry_id", "sub_industry",
    "public_company_flag", "size_metadata", "revenue_metadata",
    "jurisdiction_presence", "entity_type", "tenant_id",
}
# Fields the importer is allowed to fill on an EXISTING org — additively, into
# NULLs only. `name`, `industry`, `industry_id`, `slug` are deliberately excluded:
# they are never overwritten or draft-applied on an existing organization.
ENRICHABLE_COLUMNS = {"domain", "public_company_flag", "size_metadata", "revenue_metadata"}

ALIAS_COLUMNS = {"alias_type", "value", "organization_id", "match_confidence", "source_record_id"}


# ── normalization helpers (module-level = unit-testable) ─────────────

def normalize_domain(raw: str | None) -> str | None:
    """lowercase, drop scheme/userinfo/port/path, strip a leading www(\\d*). — so
    'https://www.Apple.com/investor' and 'WWW.apple.com' both -> 'apple.com'."""
    if not raw:
        return None
    s = raw.strip().lower()
    if not s:
        return None
    s = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", s)     # scheme
    s = re.split(r"[/?#]", s, maxsplit=1)[0]           # path/query/fragment
    s = s.split("@")[-1]                               # userinfo
    s = s.split(":")[0]                                # port
    s = re.sub(r"^www\d*\.", "", s)                    # leading www / www2
    s = s.strip(".")
    return s or None


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "org"


def cik10(cik: str | int) -> str:
    """Zero-pad a CIK to the canonical 10 digits."""
    return str(int(str(cik).strip() or "0")).zfill(10)


# ── SIC -> industry draft map ────────────────────────────────────────

class SicIndustryMap:
    """Loads config/sic_industry_map.json and resolves a 4-digit SIC to its DRAFT
    industry_id. DRAFT: callers must not apply the result to organization.industry_id."""

    def __init__(self, ranges: list[tuple[int, int, str, str]], names: dict[str, str]):
        self._ranges = ranges
        self.industry_names = names

    @classmethod
    def load(cls, path: Path | None = None) -> "SicIndustryMap":
        data = json.loads((path or _SIC_MAP_FILE).read_text(encoding="utf-8"))
        ranges = []
        for r in data.get("ranges", []):
            ranges.append((int(r["sic_low"]), int(r["sic_high"]),
                           r["industry_id"], r.get("industry_name", "")))
        return cls(ranges, dict(data.get("industries", {})))

    def resolve(self, sic: str | None) -> tuple[str | None, str | None]:
        """Return (industry_id, industry_name) for a SIC, or (None, None). DRAFT."""
        if not sic:
            return None, None
        try:
            code = int(str(sic).strip())
        except ValueError:
            return None, None
        for lo, hi, iid, name in self._ranges:
            if lo <= code <= hi:
                return iid, name
        return None, None

    def mapped_industry_ids(self) -> list[str]:
        seen: list[str] = []
        for _, _, iid, _ in self._ranges:
            if iid not in seen:
                seen.append(iid)
        return seen


# ── OrgStore port (entity resolution + additive writes) ──────────────

class OrgStore(abc.ABC):
    """Everything the connector needs to resolve/create/enrich organizations and
    write aliases. Implemented by SupabaseOrgStore (prod) and a fake (tests)."""

    @abc.abstractmethod
    def find_org_id_by_alias(self, alias_type: str, value: str) -> str | None: ...

    @abc.abstractmethod
    def find_org_id_by_domain(self, normalized_domain: str) -> str | None:
        """Match an EXISTING org by its (normalized) organization.domain — catches
        peers already in the table that have no alias rows yet."""

    @abc.abstractmethod
    def find_org_id_by_slug(self, slug: str) -> str | None: ...

    @abc.abstractmethod
    def get_org(self, org_id: str) -> dict | None: ...

    @abc.abstractmethod
    def create_org(self, fields: dict) -> str:
        """Insert a new organization; return its organization_id. Must satisfy the
        UNIQUE(slug) constraint (implementations retry with a suffixed slug)."""

    @abc.abstractmethod
    def patch_org_nulls(self, org_id: str, fields: dict) -> list[str]:
        """Set each of `fields` ONLY where the org's current column is NULL. Returns
        the list of columns actually filled. Never overwrites a non-null field."""

    @abc.abstractmethod
    def upsert_alias(self, row: dict) -> bool:
        """Insert an alias with ON CONFLICT(alias_type,value) DO NOTHING. Returns
        True iff a new row was inserted."""


class SupabaseOrgStore(OrgStore):
    """Production OrgStore over PostgREST (service-role)."""

    def __init__(self, timeout: float = 30.0):
        self._url = settings.supabase_url
        self._timeout = timeout

    def _h(self, **extra) -> dict:
        return {**get_service_headers(), **extra}

    def _rest(self, path: str) -> str:
        return f"{self._url}/rest/v1/{path}"

    def find_org_id_by_alias(self, alias_type: str, value: str) -> str | None:
        r = httpx.get(self._rest(
            f"organization_alias?select=organization_id&alias_type=eq.{alias_type}"
            f"&value=eq.{_q(value)}&limit=1"), headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0]["organization_id"] if rows and rows[0].get("organization_id") else None

    def find_org_id_by_domain(self, normalized_domain: str) -> str | None:
        # Match either the exact stored domain or the www-prefixed form.
        r = httpx.get(self._rest(
            f"organization?select=organization_id,domain"
            f"&or=(domain.eq.{_q(normalized_domain)},domain.eq.{_q('www.' + normalized_domain)})"
            f"&limit=1"), headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0]["organization_id"] if rows else None

    def find_org_id_by_slug(self, slug: str) -> str | None:
        r = httpx.get(self._rest(f"organization?select=organization_id&slug=eq.{_q(slug)}&limit=1"),
                      headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0]["organization_id"] if rows else None

    def get_org(self, org_id: str) -> dict | None:
        r = httpx.get(self._rest(f"organization?select=*&organization_id=eq.{org_id}&limit=1"),
                      headers=self._h(), timeout=self._timeout)
        rows = r.json() if r.status_code < 300 else []
        return rows[0] if rows else None

    def create_org(self, fields: dict) -> str:
        payload = {k: v for k, v in fields.items() if k in ORG_COLUMNS}
        base_slug = payload.get("slug") or slugify(payload.get("name", "org"))
        for attempt in range(4):
            payload["slug"] = base_slug if attempt == 0 else f"{base_slug}-{fields.get('_cik', attempt)}-{attempt}"
            r = httpx.post(self._rest("organization"),
                           headers=self._h(**{"Content-Type": "application/json",
                                              "Prefer": "return=representation"}),
                           json=payload, timeout=self._timeout)
            if r.status_code < 300:
                return r.json()[0]["organization_id"]
            body = (r.text or "")
            if r.status_code == 409 and ("slug" in body or "organization_slug_key" in body):
                continue                              # slug collision — retry suffixed
            raise RuntimeError(f"organization insert failed: HTTP {r.status_code}")
        raise RuntimeError("organization insert failed: slug collisions exhausted")

    def patch_org_nulls(self, org_id: str, fields: dict) -> list[str]:
        current = self.get_org(org_id) or {}
        to_set = {k: v for k, v in fields.items()
                  if k in ENRICHABLE_COLUMNS and v is not None and current.get(k) is None}
        if not to_set:
            return []
        r = httpx.patch(self._rest(f"organization?organization_id=eq.{org_id}"),
                        headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                        json=to_set, timeout=self._timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"organization enrich patch failed: HTTP {r.status_code}")
        return sorted(to_set)

    def upsert_alias(self, row: dict) -> bool:
        payload = {k: v for k, v in row.items() if k in ALIAS_COLUMNS}
        r = httpx.post(self._rest("organization_alias?on_conflict=alias_type,value"),
                       headers=self._h(**{"Content-Type": "application/json",
                                          "Prefer": "resolution=ignore-duplicates,return=representation"}),
                       json=[payload], timeout=self._timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"organization_alias upsert failed: HTTP {r.status_code}")
        inserted = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
        return len(inserted) > 0


def _q(value: str) -> str:
    """PostgREST value-encode: wrap in double quotes so commas/spaces are literal."""
    return '"' + str(value).replace('"', '\\"') + '"'


# ── the connector ────────────────────────────────────────────────────

class EdgarBulkConnector(Connector):
    family = "sec_edgar"
    source_type = "corporate_filing"
    parser_version = "edgar-bulk-submissions-v1"
    parser_description = "SEC EDGAR bulk submissions metadata -> organization + organization_alias"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, *,
                 limit: int | None = None, industries: list[str] | None = None,
                 bulk_path: str | None = None, org_store: OrgStore | None = None,
                 sic_map: SicIndustryMap | None = None, roster: list[dict] | None = None,
                 allow_ticker_fetch: bool = True):
        cfg = (registry_row or {}).get("config") or {}
        self._bulk = Path(bulk_path or cfg.get("edgar_bulk_path") or settings.edgar_bulk_path or "")
        self._limit = limit
        self._store = org_store or SupabaseOrgStore()
        self._sic = sic_map or SicIndustryMap.load()
        self._roster = roster                          # test-injectable; else loaded in fetch()
        self._allow_ticker_fetch = allow_ticker_fetch
        # target industry_ids: caller-supplied subset, else every mapped industry
        want = industries or self._sic.mapped_industry_ids()
        self._industries = set(want)
        # metrics
        self._companies = 0
        self._orgs_created = 0
        self._orgs_enriched = 0
        self._orgs_unchanged = 0
        self._aliases_inserted = 0
        self._industry_counts: dict[str, int] = {}
        self._samples: list[dict] = []                 # up to 10 created-org summaries
        self._warnings: list[str] = []

    # ── roster (company_tickers.json — the one permitted network fetch) ───
    def _maybe_roster(self) -> list[dict] | None:
        """Return the ticker roster from a local company_tickers.json, else fetch it
        once from sec.gov (permitted exception), else None → caller scans the bulk
        submissions directory locally."""
        if self._roster is not None:
            return self._roster
        local = self._bulk / "company_tickers.json"
        raw: bytes | None = None
        if local.exists():
            raw = local.read_bytes()
        elif self._allow_ticker_fetch:
            try:
                log.info("company_tickers.json missing from bulk — fetching once from sec.gov")
                with httpx.Client(timeout=60, follow_redirects=True,
                                  headers={"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"}) as c:
                    resp = c.get(_COMPANY_TICKERS_URL)
                    resp.raise_for_status()
                    raw = resp.content
                try:
                    local.write_bytes(raw)           # cache into the bulk dir for next run
                except OSError:
                    log.warning("could not cache company_tickers.json into bulk dir (continuing)")
            except Exception as e:                    # noqa: BLE001 — fall back to local scan
                log.warning("company_tickers.json fetch failed (%s); scanning local submissions dir",
                            type(e).__name__)
                return None
        else:
            return None
        obj = json.loads(raw)
        # {"0": {"cik_str":320193,"ticker":"AAPL","title":"Apple Inc."}, ...}
        rows = obj.values() if isinstance(obj, dict) else obj
        self._roster = [{"cik": cik10(r["cik_str"]), "ticker": r.get("ticker", ""),
                         "title": r.get("title", "")} for r in rows if r.get("cik_str") is not None]
        return self._roster

    def _submission_path(self, cik: str) -> Path:
        return self._bulk / "submissions" / f"CIK{cik}.json"

    def _candidate_ciks(self):
        """Yield (cik, roster_entry|None). Prefer the ticker roster; fall back to a
        local scan of submissions/ main files (shards like CIK…-submissions-001.json
        are skipped). `dir_scan` is True when we're walking the directory (then only
        ticker-bearing companies are kept, matching the roster's scope)."""
        roster = self._maybe_roster()
        if roster is not None:
            for e in roster:
                yield e["cik"], e, False
            return
        subdir = self._bulk / "submissions"
        for p in sorted(subdir.glob("CIK*.json")):
            if "-" in p.name:                         # shard file, not the main metadata
                continue
            yield p.name[3:-5], None, True            # 'CIK{cik}.json' -> cik

    # ── fetch: scan local submissions, keep companies in mapped industries ──
    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        missing = 0
        for cik, entry, dir_scan in self._candidate_ciks():
            if self._limit is not None and len(items) >= self._limit:
                break
            path = self._submission_path(cik)
            if not path.exists():
                missing += 1
                continue
            data = path.read_bytes()
            try:
                meta = json.loads(data)
            except json.JSONDecodeError:
                self._warnings.append(f"CIK{cik}: unparseable submissions JSON (skipped)")
                continue
            # directory-scan fallback: restrict to ticker-bearing companies (the
            # roster's scope) so we don't sweep in ~1M funds/trusts.
            if dir_scan and not [t for t in (meta.get("tickers") or []) if t]:
                continue
            sic = (meta.get("sic") or "").strip()
            industry_id, _ = self._sic.resolve(sic)
            if industry_id is None or industry_id not in self._industries:
                continue                              # out of scope for this run
            self._industry_counts[industry_id] = self._industry_counts.get(industry_id, 0) + 1
            items.append(RawItem(
                data=data, content_type="application/json",
                source_url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                natural_key=f"cik:{cik}",
                title=meta.get("name") or (entry or {}).get("title") or f"CIK{cik}",
                jurisdiction="US"))
        if missing:
            log.info("edgar fetch: %d roster CIKs had no local submissions file (skipped)", missing)
        log.info("edgar fetch: %d companies in scope (industries=%s, limit=%s)",
                 len(items), sorted(self._industries), self._limit)
        return items

    # ── parse: submissions metadata -> one normalized company record ──
    def parse(self, item: RawItem) -> list[dict]:
        meta = json.loads(item.data)                  # untrusted local data: parse only
        cik = cik10(meta.get("cik") or item.natural_key.split(":")[-1])
        name = (meta.get("name") or "").strip() or f"CIK{cik}"
        sic = (meta.get("sic") or "").strip()
        industry_id, industry_name = self._sic.resolve(sic)
        domain = normalize_domain(meta.get("website") or meta.get("investorWebsite"))

        tickers = [t for t in (meta.get("tickers") or []) if t]
        exchanges = [e for e in (meta.get("exchanges") or []) if e]
        former_names = [fn.get("name", "").strip() for fn in (meta.get("formerNames") or [])
                        if fn.get("name")]

        # size / sophistication INPUTS only — no scores computed here.
        size_metadata = _prune({
            "sic": sic or None,
            "sic_description": (meta.get("sicDescription") or "").strip() or None,
            "filer_category": (meta.get("category") or "").strip() or None,
            "entity_type_sec": (meta.get("entityType") or "").strip() or None,
            "state_of_incorporation": (meta.get("stateOfIncorporation") or "").strip() or None,
            "exchanges": exchanges or None,
            "employee_count": _as_int(meta.get("employeeCount")),   # not usually in submissions
            # DRAFT suggestion recorded as an INPUT only — NOT applied to industry_id.
            "sic_industry_draft": industry_id,
            "sic_industry_draft_mapped_by": "draft" if industry_id else None,
            "source": "sec_edgar_submissions",
        })
        revenue = _as_num(meta.get("revenue"))        # not usually in submissions
        revenue_metadata = {"revenue": revenue, "source": "sec_edgar_submissions"} if revenue is not None else None

        aliases = [{"alias_type": "cik", "value": cik, "match_confidence": 1.0}]
        for t in tickers:
            aliases.append({"alias_type": "ticker", "value": t.upper(), "match_confidence": 1.0})
        aliases.append({"alias_type": "legal_name", "value": name, "match_confidence": 1.0})
        for fn in former_names:
            aliases.append({"alias_type": "legal_name", "value": fn, "match_confidence": 1.0})
        if domain:
            aliases.append({"alias_type": "domain", "value": domain, "match_confidence": 1.0})

        org_fields = _prune({
            "name": name,
            "slug": slugify(name),
            "domain": domain,
            "industry": "unknown",                    # NOT NULL; draft SIC map NOT applied
            "industry_id": None,                      # draft mapping stays unapplied (expert-owned)
            "public_company_flag": True,              # SEC registrant
            "size_metadata": size_metadata or None,
            "revenue_metadata": revenue_metadata,
            "entity_type": "peer",                    # benchmark peer
            "_cik": cik,                              # helper for slug de-collision (stripped before write)
        })
        return [{
            "cik": cik, "name": name, "domain": domain,
            "industry_id": industry_id, "industry_name": industry_name,
            "org_fields": org_fields, "aliases": aliases,
        }]

    # ── upsert: entity-resolve, additively enrich, write aliases ──────
    def upsert(self, records: list[dict]) -> None:
        for rec in records:
            self._companies += 1
            src_id = rec.get("source_record_id")     # attached by the framework
            org_id = self._resolve_org(rec)
            org_fields = dict(rec["org_fields"])
            org_fields.pop("_cik", None)

            if org_id is None:
                fields = {k: v for k, v in rec["org_fields"].items()}
                org_id = self._store.create_org(fields)
                self._orgs_created += 1
                if len(self._samples) < 10:
                    self._samples.append({
                        "organization_id": org_id, "cik": rec["cik"], "name": rec["name"],
                        "domain": rec["domain"], "industry": "unknown", "industry_id": None,
                        "sic_industry_draft": rec["industry_id"],
                        "filer_category": (rec["org_fields"].get("size_metadata") or {}).get("filer_category"),
                    })
            else:
                filled = self._store.patch_org_nulls(org_id, org_fields)
                if filled:
                    self._orgs_enriched += 1
                else:
                    self._orgs_unchanged += 1

            for alias in rec["aliases"]:
                row = {**alias, "organization_id": org_id, "source_record_id": src_id}
                if self._store.upsert_alias(row):
                    self._aliases_inserted += 1

    def _resolve_org(self, rec: dict) -> str | None:
        """cik alias -> ticker alias -> domain alias -> existing org.domain -> slug.
        First hit wins; None means create a new org."""
        s = self._store
        oid = s.find_org_id_by_alias("cik", rec["cik"])
        if oid:
            return oid
        for alias in rec["aliases"]:
            if alias["alias_type"] == "ticker":
                oid = s.find_org_id_by_alias("ticker", alias["value"])
                if oid:
                    return oid
        if rec["domain"]:
            oid = s.find_org_id_by_alias("domain", rec["domain"]) or s.find_org_id_by_domain(rec["domain"])
            if oid:
                return oid
        return s.find_org_id_by_slug(rec["org_fields"]["slug"])

    # ── run metrics folded into the ingestion_run ─────────────────────
    def record_counts(self) -> dict:
        return {"seen": self._companies, "new": self._orgs_created,
                "changed": self._orgs_enriched, "skipped": self._orgs_unchanged}

    def run_warnings(self) -> list[str]:
        return list(self._warnings)

    @property
    def industry_counts(self) -> dict[str, int]:
        return dict(self._industry_counts)

    @property
    def samples(self) -> list[dict]:
        return list(self._samples)

    @property
    def metrics(self) -> dict:
        return {"companies": self._companies, "orgs_created": self._orgs_created,
                "orgs_enriched": self._orgs_enriched, "orgs_unchanged": self._orgs_unchanged,
                "aliases_inserted": self._aliases_inserted,
                "industry_counts": dict(self._industry_counts)}


def _prune(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None or k in ("industry_id", "revenue_metadata")}


def _as_int(v) -> int | None:
    try:
        return int(str(v).replace(",", "")) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _as_num(v) -> float | None:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None
