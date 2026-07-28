"""F-004 enforcement correlation — deepened to real embedding similarity against
RESOLVED enforcement entities only (no weight change).

Covers: (a) the live query scopes to resolution_status=resolved; (b) a clause
semantically close to a resolved FTC action embeds closer than a control (real
model); (c) higher ES yields a higher F-004 score (monotonic).
"""

import numpy as np
import pytest

from app.services.scoring.formulas import EnforcementMatch, compute_f004


# ── (a) RESOLVED-only filter in the live enforcement query ───

class _Resp:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self):
        self.urls = []

    async def get(self, url, headers=None):
        self.urls.append(url)
        if "enforcement_record" in url:
            # Return one resolved record (the query itself is what we assert on).
            return _Resp([{"enforcement_id": "E1", "regulator_id": "FTC",
                           "embedding": [0.1] * 384}])
        return _Resp([])


class _FakeModel:
    def __init__(self, *a, **k):
        pass

    def encode(self, texts, show_progress_bar=False):
        return np.array([[0.1] * 384 for _ in texts], dtype=np.float32)


@pytest.mark.anyio
async def test_f004_live_query_scopes_to_resolved(monkeypatch):
    import sentence_transformers
    import app.services.live_scoring as LS
    from app.services.intake.decompose import DecomposedClause, DecomposedNotice

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _FakeModel)

    notice = DecomposedNotice(clauses=[DecomposedClause(
        clause_id="c1", section_id="s1",
        raw_text="We share your personal information with third-party advertising partners.",
        normalized_text="we share your personal information with third-party advertising partners.",
        category="data_sharing", ambiguity_score=0.0, readability_score=0.5, nlp_confidence=0.8,
    )])
    regulators = [{"id": "FTC", "rpw": {"data_sharing": 0.9}, "efw": 0.9}]

    client = _FakeClient()
    score, lineage = await LS._compute_live_f004(client, {}, notice, regulators)

    enf_urls = [u for u in client.urls if "enforcement_record" in u]
    assert enf_urls, "F-004 should query enforcement_record"
    assert all("resolution_status=eq.resolved" in u for u in enf_urls), \
        "F-004 must correlate against RESOLVED enforcement only"


# ── (b) Real semantic similarity: close clause > control ─────

def test_clause_near_resolved_action_embeds_closer_than_control():
    from app.services.embeddings import embed_texts

    resolved_ftc = ("The FTC alleged the company shared consumers' personal information "
                    "with third-party advertisers without adequate notice or consent.")
    close_clause = ("We share your personal information with third-party advertising "
                    "partners for targeted marketing purposes.")
    control_clause = ("We bake fresh sourdough bread every morning using locally milled "
                      "organic flour and filtered water.")

    v_enf, v_close, v_control = embed_texts([resolved_ftc, close_clause, control_clause])
    # embed_texts normalizes → cosine is the dot product.
    es_close = float(np.dot(v_close, v_enf))
    es_control = float(np.dot(v_control, v_enf))

    assert es_close > es_control, f"close {es_close:.3f} should exceed control {es_control:.3f}"
    assert es_close >= 0.30, f"close ES {es_close:.3f} should clear the F-004 floor"


# ── (c) Higher ES → higher F-004 score (monotonic, no weight change) ─

def test_higher_es_yields_higher_f004_score():
    high = compute_f004([EnforcementMatch("c", "E1", "FTC", cosine_similarity=0.80,
                                          rpw=0.9, efw=0.9, domain="data_sharing")])
    low = compute_f004([EnforcementMatch("c", "E1", "FTC", cosine_similarity=0.40,
                                         rpw=0.9, efw=0.9, domain="data_sharing")])
    assert high.score > low.score
