"""Reusable source-ingestion connector framework (F02 v2).

Lifecycle per source item: fetch → hash → raw-store → (skip | new | version) →
parse → normalize → upsert. See base.Connector and runner.run.
"""
