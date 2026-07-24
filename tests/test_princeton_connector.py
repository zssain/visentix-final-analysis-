"""Princeton-Leuven curated-corpus connector — golden CSV import, org-resolution vs
benchmark-only creation, dedupe, idempotency, and the no-benchmark_membership-writes
guarantee. No network, no live DB."""
import csv
import inspect
import shutil
from pathlib import Path

from app.services.ingestion import runner
from app.services.ingestion.connectors import princeton as mod
from app.services.ingestion.connectors.princeton import (
    PrincetonConnector, freshness_weight, snapshot_date,
)
from tests.ingestion_fakes import TypedFakeBackend as FakeBackend

FIX = Path(__file__).parent / "fixtures" / "princeton_sample.csv"
ROWS = list(csv.DictReader(FIX.open(encoding="utf-8")))


class FakePrincetonWriter:
    """In-memory PrincetonWriter double. `existing` maps domain -> org_id for
    domains that already resolve; others create a benchmark-only org."""

    def __init__(self, existing: dict | None = None):
        self.existing = existing or {}
        self.created_orgs: list[dict] = []
        self.notices: list[dict] = []
        self.sections = 0
        self.clauses = 0
        self._seq = 0

    def resolve_or_create_org(self, domain, sector, source_id):
        if domain in self.existing:
            return self.existing[domain], False
        self._seq += 1
        oid = f"org-{self._seq}"
        self.created_orgs.append({"organization_id": oid, "domain": domain, "sector": sector,
                                  "origin": "princeton_leuven", "source_id": source_id})
        return oid, True

    def create_notice(self, org_id, rec):
        nid = f"notice-{len(self.notices)}"
        self.notices.append({"notice_id": nid, "org_id": org_id, "domain": rec["domain"],
                             "effective_date": rec["effective_date"], "content_hash": rec["content_hash"]})
        return nid

    def persist_notice_body(self, notice_id, notice):
        self.sections += len(notice.sections)
        self.clauses += len(notice.clauses)


def _run(rows, writer, backend=None):
    conn = PrincetonConnector(rows=rows, writer=writer)
    return runner.run(backend or FakeBackend(), conn, politeness_seconds=0), conn


# ── Freshness honesty ────────────────────────────────────────────────

def test_freshness_truthful_for_2019():
    from datetime import date
    assert freshness_weight("2019B", date(2026, 7, 23)) == 0.0     # ~7y old → excluded by CQS
    assert freshness_weight("2025A", date(2026, 7, 23)) > 0.0      # recent → non-zero
    assert snapshot_date("2019B") == "2019-07-01"
    assert snapshot_date("2019A") == "2019-01-01"


# ── Golden-file import ───────────────────────────────────────────────

def test_golden_import(tmp_path):
    # sector = the FILE name; two sector files, so counts split by filename (not the
    # per-row `category` column, which holds the dataset's compound tags).
    shutil.copy(FIX, tmp_path / "healthcare.csv")           # 5 rows → sector 'healthcare'
    shutil.copy(FIX, tmp_path / "retail.csv")               # same 5 rows → dedupe drops them
    be = FakeBackend()
    conn = PrincetonConnector(extract_dir=str(tmp_path), writer=FakePrincetonWriter())
    res = runner.run(be, conn, politeness_seconds=0)
    assert res.outcome == "ok"
    assert conn.metrics["notices"] == 5                     # 10 rows, 5 unique (domain,sha) → dedupe
    assert conn.metrics["clauses"] > 0
    # source_record: dataset type + TRUTHFUL freshness (0 for the 2018/2019 snapshots)
    srs = list(be.source_records.values())
    assert len(srs) == 5
    assert all(s["source_type"] == "dataset" for s in srs)
    assert all(s["freshness_weight"] == 0.0 for s in srs)
    assert all("reliability_tier=2" in s["notes"] for s in srs)
    assert all("category=" in s["notes"] for s in srs)      # dataset tag preserved in provenance
    # sector comes from the filename; the healthcare file wins the (domain,sha) dedupe
    assert set(conn.metrics["sector_counts"]) == {"healthcare"}


# ── Org resolution vs benchmark-only creation ────────────────────────

def test_org_resolution_vs_benchmark_only():
    w = FakePrincetonWriter(existing={"paypal.com": "org-existing-paypal"})
    _run(ROWS, w)
    # paypal.com matched an existing org; the other 4 domains created benchmark-only orgs
    assert w.notices[1]["org_id"] == "org-existing-paypal"
    created_domains = {o["domain"] for o in w.created_orgs}
    assert created_domains == {"healthportal.com", "shopmart.com", "edulearn.org", "streamly.com"}
    assert all(o["origin"] == "princeton_leuven" for o in w.created_orgs)
    # every created org's domain alias carries the dataset source_record lineage
    assert all(o["source_id"] and o["source_id"].startswith("princeton_leuven:") for o in w.created_orgs)


# ── Dedupe (domain, policy_text sha256) ──────────────────────────────

def test_dedupe_same_domain_same_text():
    dup = ROWS + [dict(ROWS[0])]              # exact duplicate of row 0
    w = FakePrincetonWriter()
    _res, conn = _run(dup, w)
    assert conn.metrics["notices"] == 5      # 6 rows in, duplicate collapsed to 5
    assert len(w.notices) == 5


def test_distinct_text_same_domain_not_deduped():
    variant = dict(ROWS[0]); variant["policy_text"] = ROWS[0]["policy_text"] + "\n\nExtra clause about biometric data."
    w = FakePrincetonWriter()
    _res, conn = _run(ROWS + [variant], w)
    assert conn.metrics["notices"] == 6      # different sha for same domain → kept


# ── Idempotent re-run ────────────────────────────────────────────────

def test_idempotent_rerun():
    be = FakeBackend()
    w1 = FakePrincetonWriter()
    _run(ROWS, w1, backend=be)
    assert len(w1.notices) == 5
    w2 = FakePrincetonWriter()
    res2, _ = _run(ROWS, w2, backend=be)     # same rows, same backend → all skipped
    assert res2.new == 0 and len(w2.notices) == 0


# ── NEVER writes benchmark_membership ────────────────────────────────

def test_no_benchmark_membership_writes():
    # static: the connector never writes benchmark_membership (no quoted table literal /
    # REST target — the docstring may MENTION it in prose, which is fine).
    src = inspect.getsource(mod)
    assert '"benchmark_membership"' not in src and "'benchmark_membership'" not in src
    assert "rest/v1/benchmark_membership" not in src and "_rest(\"benchmark_membership" not in src
    # behavioral: a run touches only source_record / privacy_notice writers, never a
    # benchmark table (the fake backend has no benchmark_membership sink at all).
    be = FakeBackend()
    _run(ROWS, FakePrincetonWriter(), backend=be)
    assert not hasattr(be, "benchmark_membership")


def test_malformed_rows_flagged_not_dropped():
    bad = ROWS + [{"domain": "", "category": "x", "last_updated": "2019B", "policy_text": "text"},
                  {"domain": "ok.com", "category": "x", "last_updated": "2019B", "policy_text": "   "}]
    res, conn = _run(bad, FakePrincetonWriter())
    assert conn.metrics["notices"] == 5
    assert any("malformed" in w for w in res.warnings)
    assert res.outcome == "partial"


def test_connector_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("princeton_leuven") is PrincetonConnector
