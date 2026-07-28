"""Server-side database clients.

Uses the SERVICE-ROLE key — this module is imported by the API server only,
never by client-facing code paths.
"""

import httpx

from app.config import settings

# Shared headers for server-side Supabase REST calls (bypasses RLS).
_SERVICE_HEADERS = {
    "apikey": settings.supabase_service_role_key,
    "Authorization": f"Bearer {settings.supabase_service_role_key}",
}


def get_service_headers() -> dict[str, str]:
    """Return a copy of service-role headers for Supabase REST calls."""
    return {**_SERVICE_HEADERS}


async def supabase_rest_get(
    table: str,
    *,
    select: str = "*",
    filters: str = "",
    limit: int = 1000,
    count: bool = False,
) -> httpx.Response:
    """Read-only GET against Supabase PostgREST."""
    headers = get_service_headers()
    if count:
        headers["Prefer"] = "count=exact"

    qs = f"select={select}&limit={limit}"
    if filters:
        qs += f"&{filters}"

    async with httpx.AsyncClient(timeout=15) as client:
        return await client.get(
            f"{settings.supabase_url}/rest/v1/{table}?{qs}",
            headers=headers,
        )


async def supabase_rest_post(
    table: str,
    payload: list[dict] | dict,
    *,
    on_conflict: str = "",
    upsert: bool = False,
) -> httpx.Response:
    """Insert rows via Supabase PostgREST."""
    headers = get_service_headers()
    headers["Content-Type"] = "application/json"
    if upsert and on_conflict:
        headers["Prefer"] = "resolution=merge-duplicates"

    url = f"{settings.supabase_url}/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"

    async with httpx.AsyncClient(timeout=15) as client:
        return await client.post(url, headers=headers, json=payload)


async def supabase_rest_patch(table: str, filters: str, payload: dict) -> httpx.Response:
    """PATCH (update) rows matching `filters` (raw PostgREST filter string)."""
    headers = get_service_headers()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=minimal"
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.patch(
            f"{settings.supabase_url}/rest/v1/{table}?{filters}",
            headers=headers, json=payload,
        )
