"""DATA-001: benchmark population version must be canonical & deterministic.

Previously ``build_population`` stamped ``benchmark_population_version`` with
``int(time.time())`` — a wall-clock value that made two identical re-scores
produce different lineage stamps. The version is now derived from the
population's actual content via the pure helper ``_population_version``.

These tests exercise the smallest unit that computes the version so they do NOT
touch the live DB.
"""

from app.services.benchmark.population import _population_version


def test_same_members_same_version():
    """Identical member set + config → identical version (determinism)."""
    ids = ["org-c", "org-a", "org-b"]
    v1 = _population_version(
        ids, population_key="Tech|High|Mature", member_profile_versions=[3, 3, 2]
    )
    v2 = _population_version(
        ids, population_key="Tech|High|Mature", member_profile_versions=[3, 3, 2]
    )
    assert v1 == v2


def test_order_independent():
    """Member ordering must not affect the identity (it's a set)."""
    a = _population_version(["org-a", "org-b", "org-c"], population_key="k")
    b = _population_version(["org-c", "org-a", "org-b"], population_key="k")
    assert a == b


def test_different_member_set_different_version():
    """A changed member set MUST produce a different version."""
    base = _population_version(["org-a", "org-b"], population_key="k")
    added = _population_version(["org-a", "org-b", "org-c"], population_key="k")
    removed = _population_version(["org-a"], population_key="k")
    assert base != added
    assert base != removed
    assert added != removed


def test_different_config_different_version():
    """Changed cohort config / profile versions / corpus → different version."""
    ids = ["org-a", "org-b"]
    base = _population_version(ids, population_key="Tech|High", member_profile_versions=[1])
    diff_key = _population_version(ids, population_key="Finance|Low", member_profile_versions=[1])
    diff_pv = _population_version(ids, population_key="Tech|High", member_profile_versions=[2])
    diff_corpus = _population_version(
        ids, population_key="Tech|High", member_profile_versions=[1], corpus_version=99
    )
    assert base != diff_key
    assert base != diff_pv
    assert base != diff_corpus


def test_stable_across_time(monkeypatch):
    """Simulate two calls 'at different times' — wall-clock must have NO effect."""
    import time as _time

    ids = ["org-a", "org-b", "org-c"]
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    v_early = _population_version(ids, population_key="k", member_profile_versions=[1])
    monkeypatch.setattr(_time, "time", lambda: 9_999_999.0)
    v_late = _population_version(ids, population_key="k", member_profile_versions=[1])
    assert v_early == v_late


def test_positive_int32_range():
    """Value must be a positive int that fits a Postgres int32 column."""
    for members in ([], ["org-a"], [f"org-{i}" for i in range(200)]):
        v = _population_version(members, population_key="k")
        assert isinstance(v, int)
        assert 0 <= v <= 0x7FFFFFFF
        # Must also survive str() for the derived_data_item (text) path.
        assert str(v).lstrip("-").isdigit()
