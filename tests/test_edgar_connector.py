"""SEC EDGAR bulk-import connector — golden-file parse, additive no-overwrite,
alias uniqueness, domain normalization, and idempotent re-run. No network, no live
DB (fake backend + fake OrgStore, both live-type-checked)."""
import json
from pathlib import Path

import pytest

from app.services.ingestion import runner
from app.services.ingestion.base import RawItem
from app.services.ingestion.connectors.edgar import (
    EdgarBulkConnector, SicIndustryMap, normalize_domain, slugify, cik10,
)
from tests.ingestion_fakes import FakeOrgStore
from tests.ingestion_fakes import TypedFakeBackend as FakeBackend

FIXDIR = Path(__file__).parent / "fixtures"
FIXTURE = (FIXDIR / "edgar_sample_submissions.json").read_bytes()
CIK = "0001800000"
URL = f"https://data.sec.gov/submissions/CIK{CIK}.json"


def _bulk_dir(tmp_path: Path, tickers: list[dict] | None = None,
              subs: dict[str, bytes] | None = None) -> Path:
    """Build a minimal local EDGAR bulk tree for fetch() to read."""
    (tmp_path / "submissions").mkdir(parents=True, exist_ok=True)
    subs = subs or {CIK: FIXTURE}
    for cik, data in subs.items():
        (tmp_path / "submissions" / f"CIK{cik}.json").write_bytes(data)
    roster = tickers or [{"cik_str": int(CIK), "ticker": "BHS", "title": "Beta Health Systems, Inc."}]
    (tmp_path / "company_tickers.json").write_bytes(
        json.dumps({str(i): r for i, r in enumerate(roster)}).encode())
    return tmp_path


def _conn(tmp_path, store=None, **kw):
    return EdgarBulkConnector(
        {"config": {}}, bulk_path=str(tmp_path), org_store=store or FakeOrgStore(),
        allow_ticker_fetch=False, **kw)


def _run(tmp_path, store, **kw):
    if not (tmp_path / "submissions").exists():       # build the default 1-company bulk
        _bulk_dir(tmp_path)
    conn = _conn(tmp_path, store, **kw)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    return res, conn


# ── Golden-file parse ───────────────────────────────────────────────

def test_golden_file_parse():
    conn = EdgarBulkConnector({"config": {}}, org_store=FakeOrgStore(), roster=[],
                              bulk_path="/nonexistent", allow_ticker_fetch=False)
    recs = conn.parse(RawItem(FIXTURE, "application/json", URL, f"cik:{CIK}"))
    assert len(recs) == 1
    r = recs[0]
    assert r["cik"] == CIK
    of = r["org_fields"]
    assert of["name"] == "Beta Health Systems, Inc."
    assert of["slug"] == "beta-health-systems-inc"
    assert of["domain"] == "betahealth.com"          # www + scheme + path stripped
    assert of["industry"] == "unknown"               # draft SIC map NOT applied
    assert of["industry_id"] is None
    assert of["public_company_flag"] is True
    sm = of["size_metadata"]
    assert sm["sic"] == "8000"
    assert sm["filer_category"] == "Large accelerated filer"
    assert sm["state_of_incorporation"] == "DE"
    assert sm["exchanges"] == ["NYSE"]
    # DRAFT suggestion recorded as an INPUT only
    assert sm["sic_industry_draft"] == "IND-03"
    assert sm["sic_industry_draft_mapped_by"] == "draft"
    # aliases: cik, ticker, current + former legal_name, domain — all confidence 1.0
    by_type = {}
    for a in r["aliases"]:
        by_type.setdefault(a["alias_type"], []).append(a["value"])
        assert a["match_confidence"] == 1.0
    assert by_type["cik"] == [CIK]
    assert by_type["ticker"] == ["BHS"]
    assert set(by_type["legal_name"]) == {"Beta Health Systems, Inc.", "Beta Health Corp"}
    assert by_type["domain"] == ["betahealth.com"]


def test_full_run_creates_org_and_aliases(tmp_path):
    store = FakeOrgStore()
    res, conn = _run(tmp_path, store)
    assert res.outcome == "ok"
    assert res.new == 1 and res.seen == 1            # one org created
    assert conn.industry_counts == {"IND-03": 1}
    assert conn.metrics["aliases_inserted"] == 5     # cik+ticker+2 legal_name+domain
    org = list(store.orgs.values())[0]
    assert org["name"] == "Beta Health Systems, Inc."
    assert org["industry"] == "unknown" and org["industry_id"] is None
    assert org["public_company_flag"] is True
    # every alias points at the created org and carries the source_record lineage
    for a in store.aliases.values():
        assert a["organization_id"] == org["organization_id"]
        assert a["source_record_id"] and a["source_record_id"].startswith("sec_edgar:")


# ── No-overwrite (additive enrichment) ──────────────────────────────

def test_existing_org_fields_survive_reimport(tmp_path):
    store = FakeOrgStore()
    # a pre-existing peer already classified by an expert, matched by domain
    existing = store.seed_org(
        name="Beta Health EXISTING", slug="beta-existing", domain="betahealth.com",
        industry="healthcare", industry_id="IND-EXPERT", public_company_flag=None,
        size_metadata=None)
    res, conn = _run(tmp_path, store)
    assert res.new == 0 and res.changed == 1         # enriched, not created
    org = store.orgs[existing]
    # canonical, expert-owned fields are UNTOUCHED
    assert org["name"] == "Beta Health EXISTING"
    assert org["industry"] == "healthcare"
    assert org["industry_id"] == "IND-EXPERT"
    # null fields were additively filled
    assert org["public_company_flag"] is True
    assert org["size_metadata"] and org["size_metadata"]["sic"] == "8000"
    assert len(store.orgs) == 1                       # no duplicate peer created


def test_enrich_never_touches_industry_when_already_set(tmp_path):
    store = FakeOrgStore()
    oid = store.seed_org(name="X", slug="x", domain="betahealth.com",
                         industry="fintech", industry_id="IND-04",
                         public_company_flag=True, size_metadata={"pre": "existing"})
    _run(tmp_path, store)
    org = store.orgs[oid]
    assert org["industry"] == "fintech" and org["industry_id"] == "IND-04"
    assert org["size_metadata"] == {"pre": "existing"}   # non-null → not overwritten


# ── Alias uniqueness (UNIQUE(alias_type, value)) ────────────────────

def test_alias_uniqueness(tmp_path):
    store = FakeOrgStore()
    _run(tmp_path, store)
    n_first = len(store.aliases)
    # same (alias_type, value) must not create a second row
    assert store.upsert_alias({"alias_type": "cik", "value": CIK,
                               "organization_id": store._new_id(), "match_confidence": 1.0,
                               "source_record_id": None}) is False
    assert len(store.aliases) == n_first
    # (type,value) pair is the key — same value under a different type is allowed
    assert store.upsert_alias({"alias_type": "legal_name", "value": CIK,
                               "organization_id": list(store.orgs)[0], "match_confidence": 1.0,
                               "source_record_id": None}) is True


# ── Domain normalization ────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("https://www.Apple.com/investor", "apple.com"),
    ("WWW.Example.COM", "example.com"),
    ("http://sub.example.com", "sub.example.com"),   # real subdomain preserved
    ("example.com/", "example.com"),
    ("https://www2.foo.com:8443/path?x=1", "foo.com"),
    ("user@host.example.com", "host.example.com"),
    ("world.com", "world.com"),                       # leading 'w' chars NOT stripped
    ("", None),
    (None, None),
    ("   ", None),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_slug_and_cik_helpers():
    assert slugify("Beta Health Systems, Inc.") == "beta-health-systems-inc"
    assert slugify("!!!") == "org"
    assert cik10(320193) == "0000320193"
    assert cik10("0001800000") == "0001800000"


# ── Idempotent re-run (unchanged bytes ⇒ 0 new) ─────────────────────

def test_idempotent_rerun(tmp_path):
    store = FakeOrgStore()
    be = FakeBackend()
    _bulk_dir(tmp_path)
    conn1 = _conn(tmp_path, store)
    runner.run(be, conn1, politeness_seconds=0)
    assert len(store.orgs) == 1
    n_alias = len(store.aliases)
    # second run over the SAME bulk (identical bytes) → framework skips the item
    conn2 = _conn(tmp_path, store)
    res2 = runner.run(be, conn2, politeness_seconds=0)
    assert res2.new == 0
    assert len(store.orgs) == 1                       # no duplicate org
    assert len(store.aliases) == n_alias             # no duplicate aliases


# ── Industry scoping + draft-map load ───────────────────────────────

def test_industry_scope_filters_out_unmapped(tmp_path):
    # an unmapped SIC (mining, 1040) must not be imported
    mining = dict(json.loads(FIXTURE)); mining["cik"] = "0002000000"; mining["sic"] = "1040"
    subs = {CIK: FIXTURE, "0002000000": json.dumps(mining).encode()}
    roster = [{"cik_str": int(CIK), "ticker": "BHS", "title": "Beta"},
              {"cik_str": 2000000, "ticker": "GLD", "title": "Miner"}]
    tmp = _bulk_dir(tmp_path, tickers=roster, subs=subs)
    store = FakeOrgStore()
    res, conn = _run(tmp, store)
    assert conn.industry_counts == {"IND-03": 1}     # only the healthcare company
    assert res.new == 1


def test_all_industries_imports_unmapped_sic(tmp_path):
    # alias-first mode: a company whose SIC is unmapped (mining 1040) is still
    # imported, with industry_id NULL and counted under 'unmapped'.
    mining = dict(json.loads(FIXTURE)); mining["cik"] = "0002000000"; mining["sic"] = "1040"
    mining["name"] = "Goldstrike Mining Corp"                # a fully distinct entity:
    mining["tickers"] = ["GLD"]; mining["formerNames"] = []  # no shared ticker/legal_name
    mining["website"] = ""; mining["investorWebsite"] = ""   # no shared domain
    subs = {CIK: FIXTURE, "0002000000": json.dumps(mining).encode()}
    roster = [{"cik_str": int(CIK), "ticker": "BHS", "title": "Beta"},
              {"cik_str": 2000000, "ticker": "GLD", "title": "Goldstrike"}]
    tmp = _bulk_dir(tmp_path, tickers=roster, subs=subs)
    store = FakeOrgStore()
    res, conn = _run(tmp, store, all_industries=True)
    assert res.new == 2                               # both imported, incl. unmapped SIC
    assert conn.industry_counts == {"IND-03": 1, "unmapped": 1}
    miner = [o for o in store.orgs.values() if o["name"] == "Goldstrike Mining Corp"][0]
    assert miner["industry"] == "unknown" and miner["industry_id"] is None


def test_explicit_industry_subset(tmp_path):
    store = FakeOrgStore()
    # scope to financials only → the healthcare fixture is out of scope
    res, conn = _run(tmp_path, store, industries=["IND-04"])
    assert conn.industry_counts == {}
    assert res.new == 0


def test_sic_map_is_draft():
    m = SicIndustryMap.load()
    assert m.resolve("8000") == ("IND-03", "Healthcare & Life Sciences")
    assert m.resolve("5300")[0] == "IND-01"
    assert m.resolve("7372")[0] == "IND-02"
    assert m.resolve("6021")[0] == "IND-04"
    assert m.resolve("9999") == (None, None)         # unmapped
    assert m.resolve(None) == (None, None)


def test_connector_is_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("sec_edgar") is EdgarBulkConnector
