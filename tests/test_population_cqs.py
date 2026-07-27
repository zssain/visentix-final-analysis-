"""Dynamic-population CQS gate (F03 parity, Rule 6 — Stage-3).

build_population must exclude CQS-ineligible orgs (no fresh open_web notice) from
the benchmark population, matching the F03 demo-cohort gate. Guards against the
rehearsal regression where a live org was benchmarked against stale-corpus orgs.
"""

import pytest

from app.services.benchmark.population import build_population

# Identical tiers → high similarity, so inclusion turns purely on the CQS gate.
_TIERS = dict(rss_tier="Moderate", pgms_tier="Developing", osi_tier="Developing",
              dsi_tier="Low", ehp_tier="Clean", aigms_tier="Minimal")


def _profile(oid, **extra):
    return {"organization_id": oid, "pgms": 50, "rss": 50, "profile_version": 1,
            "confidence_score": 0.6, "industry_id": "IND-07", **_TIERS, **extra}


class _Resp:
    def __init__(self, data):
        self.status_code = 200
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    """Routes client.get by URL fragment to canned rows."""
    async def get(self, url, headers=None):
        if "organization_intelligence_profile" in url:
            return _Resp([_profile("T"), _profile("P1"), _profile("P2"), _profile("P3")])
        if "privacy_notice" in url and "open_web" in url:
            # P1, P2 are CQS-fresh; P3 is NOT (stale corpus); T need not be.
            return _Resp([{"organization_id": "P1"}, {"organization_id": "P2"}])
        if "/organization?" in url or url.rstrip("/").endswith("organization"):
            return _Resp([
                {"organization_id": "T", "industry": "retail", "name": "Target"},
                {"organization_id": "P1", "industry": "retail", "name": "Peer1"},
                {"organization_id": "P2", "industry": "retail", "name": "Peer2"},
                {"organization_id": "P3", "industry": "retail", "name": "Peer3 (stale)"},
            ])
        return _Resp([])


@pytest.mark.anyio
async def test_population_excludes_cqs_ineligible_orgs():
    target = _profile("T", organization_id="T", industry="retail")
    pop = await build_population(_FakeClient(), target)

    member_ids = {m["organization_id"] for m in pop["members"]}
    assert "P1" in member_ids and "P2" in member_ids       # CQS-fresh included
    assert "P3" not in member_ids                            # CQS-excluded held out
    assert pop["cqs_excluded"] == 1
    assert any(r.startswith("cqs_gated_excluded_") for r in pop["relaxations"])
