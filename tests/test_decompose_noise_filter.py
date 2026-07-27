"""Decompose-v2 noise-filter tests (F01).

Covers the approved deterministic noise rule (DECISION-NEEDED.md Part 1):
noise clauses are KEPT + flagged (never deleted), excluded from scoring counts,
lineage intact; the seq=9-style tie-break (uncertain → not noise); and the
value-identical Option-1 config move of the saturation constants.
"""

from uuid import uuid4

from app.services.intake.decompose import (
    DECOMPOSE_VERSION,
    DecomposedClause,
    DecomposedNotice,
    _section_structural_noise,
    decompose,
)
from app.services.pipeline import score_notice
from app.services.profiling.live_profile import (
    _AIGMS_SAT,
    _DSI_SAT,
    _PGMS_SAT,
    OrgProfileInput,
    compute_pgms,
)
from tests.test_live_pipeline import (
    F002_THRESHOLDS,
    F010_WEIGHTS,
    JW,
    PEER_SCORES,
    SAMPLE_REGULATORS,
)

# A notice mixing real disclosure sentences with heading/metadata/list-fragment noise.
NOISY_NOTICE = """# Privacy Notice

Last Updated: April 28, 2026

INTRODUCTION

The 1-800-Flowers family of brands respects your privacy and collects your name, email address, and browsing data when you use our services for analytics and advertising.

why we gather information about you;

how we collect it;

We share your personal information with third-party service providers who help us operate our platform and may disclose data to advertising partners.

You have the right to access, delete, and correct your personal data at any time.
"""


# ── Structural predicate unit checks ─────────────────────────

def test_predicate_markdown_heading():
    assert _section_structural_noise("# Privacy Notice") == "heading_only"


def test_predicate_metadata_before_short_label():
    # A 5-word date stamp must read as 'metadata', not 'heading_only'.
    assert _section_structural_noise("Last Updated: April 28, 2026") == "metadata"


def test_predicate_title_only():
    assert _section_structural_noise("INTRODUCTION") == "heading_only"


def test_predicate_list_fragment():
    assert _section_structural_noise("why we gather information about you;") == "list_fragment"


def test_predicate_substantive_sentence_is_not_noise():
    assert _section_structural_noise(
        "We collect your email address and browsing data when you use our services."
    ) is None


def test_tiebreak_list_continuation_not_noise():
    # seq=9-style: >12 words, no trailing ';'/':' → uncertain → NOT noise.
    text = ("the choices you may have regarding the personal information we collect "
            "and how you can exercise them")
    assert _section_structural_noise(text) is None


# ── Kept + flagged (never deleted) ───────────────────────────

def test_noise_clauses_kept_and_flagged():
    n = decompose(NOISY_NOTICE)
    noise = [c for c in n.clauses if c.is_noise]
    substantive = [c for c in n.clauses if not c.is_noise]
    assert noise, "expected some noise clauses"
    assert substantive, "expected some substantive clauses"
    # Every noise clause carries a reason and is still a real, retrievable row.
    for c in noise:
        assert c.noise_reason
        assert c.clause_id and c.section_id
        assert c.category  # still classified → lineage intact
    reasons = {c.noise_reason for c in noise}
    assert any(r.startswith(("heading_only", "section:heading_only", "clause_fragment",
                             "section:metadata", "section:list_fragment")) for r in reasons)


def test_substantive_sentences_not_flagged():
    n = decompose(NOISY_NOTICE)
    kept = [c for c in n.clauses if not c.is_noise]
    joined = " ".join(c.raw_text.lower() for c in kept)
    assert "third-party service providers" in joined
    assert "right to access" in joined
    # The heading/metadata/list fragments are NOT among substantive clauses.
    assert not any(c.raw_text.strip().startswith("#") for c in kept)
    assert not any(c.raw_text.strip().lower().startswith("last updated") for c in kept)


def test_no_clause_is_dropped():
    # decompose-v2 keeps sub-20-char fragments (was: silently dropped).
    n = decompose("# H\n\nok\n\nWe collect your email address for account security purposes.")
    texts = [c.raw_text for c in n.clauses]
    assert "ok" in texts  # kept, flagged
    frag = next(c for c in n.clauses if c.raw_text == "ok")
    assert frag.is_noise and frag.noise_reason == "clause_fragment"


def test_deterministic_flags():
    a = decompose(NOISY_NOTICE)
    b = decompose(NOISY_NOTICE)
    assert [c.is_noise for c in a.clauses] == [c.is_noise for c in b.clauses]
    assert [c.noise_reason for c in a.clauses] == [c.noise_reason for c in b.clauses]


def test_duplicate_section_flagged_keeps_first():
    dup = ("We retain your personal data only for as long as necessary to provide services.")
    text = f"# A\n\n{dup}\n\n# B\n\n{dup}"
    n = decompose(text)
    subs = [c for c in n.clauses if c.raw_text.strip() == dup]
    assert len(subs) == 2
    # First kept (not noise), second flagged as a duplicate.
    assert subs[0].is_noise is False
    assert subs[1].is_noise is True and subs[1].noise_reason.startswith("section:duplicate_of:")


# ── Scoring excludes noise ───────────────────────────────────

def _clause(cat: str, is_noise: bool = False) -> DecomposedClause:
    text = f"We process {cat.replace('_', ' ')} data as described in this notice section."
    return DecomposedClause(
        clause_id=str(uuid4()), section_id="s", raw_text=text, normalized_text=text.lower(),
        category=cat, ambiguity_score=0.01, readability_score=0.5, nlp_confidence=0.8,
        is_noise=is_noise,
    )


def _score(clauses):
    return score_notice(
        organization_id="t", notice_id="t",
        notice=DecomposedNotice(clauses=clauses),
        regulators=SAMPLE_REGULATORS, jurisdiction_weights=JW,
        f002_thresholds=F002_THRESHOLDS, f010_weights=F010_WEIGHTS,
        peer_scores=PEER_SCORES, org_pgms=55.0, avg_source_reliability=0.85,
        finding_types={}, recommendations={},
    )


def test_scoring_ignores_noise_clauses():
    base = [_clause("data_sharing"), _clause("consumer_rights"), _clause("retention")]
    noisy = base + [_clause("data_sharing", is_noise=True),
                    _clause("tracking_cookies", is_noise=True)]
    sb, sn = _score(base), _score(noisy)
    # Noise clauses must not change any score, finding, or count.
    for key in ["f002", "f003", "f005", "f006", "f007", "f010"]:
        assert sb["scores"][key]["score"] == sn["scores"][key]["score"], f"{key} moved on noise"
    assert [f["code"] for f in sb["findings"]] == [f["code"] for f in sn["findings"]]


# ── Config value-identical (Option 1) ────────────────────────

def test_saturation_constants_value_identical():
    assert (_PGMS_SAT, _DSI_SAT, _AIGMS_SAT) == (3, 5, 2)


def test_profiling_noise_exclusion_matters():
    """Sanity: including noise clauses WOULD inflate a pillar to saturation — which
    is exactly what the live_scoring filter prevents by passing substantive-only."""
    clean = OrgProfileInput(organization_id="o", name="n", industry="retail", size="large",
                            geography="US", total_clauses=2,
                            clause_categories={"consumer_rights": 2})
    padded = OrgProfileInput(organization_id="o", name="n", industry="retail", size="large",
                             geography="US", total_clauses=6,
                             clause_categories={"consumer_rights": 6})
    # consumer_rights pillar saturates at 1 category * 3 = 3 clauses.
    assert compute_pgms(clean)[0] < compute_pgms(padded)[0]


def test_decompose_version_tag():
    assert DECOMPOSE_VERSION == "decompose-v2-noisefilter"
