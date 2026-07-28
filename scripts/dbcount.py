"""Exact row counts via the IPv4 pooler (psycopg).

PostgREST `count=exact` times out (HTTP 500) on the 684k-row disclosure_clause
table, so coverage reports and the matcher's ≥95% gate must count server-side.
Reuses the pooler connection resolver from the migration runner.
"""

from __future__ import annotations

import scripts.db.apply_and_record as _mig


def exact_count(where: str = "", joins: str = "", table: str = "disclosure_clause") -> int:
    """SELECT count(*) FROM <table> <joins> [WHERE <where>] — exact, no REST timeout."""
    kw, _ = _mig._conn_kwargs()
    import psycopg
    sql = f"SELECT count(*) FROM {table} dc {joins}"
    if where:
        sql += f" WHERE {where}"
    with psycopg.connect(**kw) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]
