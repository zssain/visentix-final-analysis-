"""Litigation connector skeleton — parse tests (F07 corpus growth).

Pure parse only. The connector is NOT wired to scoring; every row is reliability
'low' with NULL issue_tags until an expert weighting scheme exists.
"""

from app.services.ingestion.connectors import litigation


def test_parse_courtlistener_maps_fields_and_absolutizes_url():
    rows = litigation.parse_courtlistener([
        {"caseName": "Doe v. Acme", "court": "cand", "dateFiled": "2026-05-01",
         "absolute_url": "/opinion/123/doe-v-acme/"},
        {"caseName": "No URL case", "court": "nysd", "dateFiled": "2026-05-02"},  # dropped (no url)
    ])
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "courtlistener"
    assert r["title"] == "Doe v. Acme"
    assert r["url"] == "https://www.courtlistener.com/opinion/123/doe-v-acme/"
    assert r["issue_tags"] is None            # NULL — no taxonomy (skeleton)
    assert r["reliability"] == "low"          # NOT wired to scoring


def test_parse_rss():
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>Smith v. Corp</title><link>https://ex.com/a</link><pubDate>2026-05-03</pubDate></item>
      <item><title>No link</title></item>
    </channel></rss>"""
    rows = litigation.parse_rss(xml)
    assert len(rows) == 1
    assert rows[0]["title"] == "Smith v. Corp"
    assert rows[0]["url"] == "https://ex.com/a"
    assert rows[0]["reliability"] == "low"


def test_reliability_is_fixed_low():
    assert litigation.RELIABILITY == "low"
