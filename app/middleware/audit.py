"""Best-effort, content-free audit capture for authenticated API requests."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from app.db import supabase_rest_post
from app.logging import get_logger

log = get_logger(__name__)
_pending_writes: set[asyncio.Task] = set()


def _resource(scope: Scope) -> tuple[str, str | None, str]:
    route = scope.get("route")
    route_path = getattr(route, "path", None) or "unmatched"
    static_parts = [part for part in route_path.split("/") if part and not part.startswith("{")]
    resource_type = static_parts[0] if static_parts else "root"
    path_params = scope.get("path_params") or {}
    resource_id = str(next(iter(path_params.values()))) if path_params else None
    return resource_type, resource_id, route_path


async def _write_event(payload: dict) -> None:
    try:
        response = await supabase_rest_post("audit_event", payload)
        if response.status_code >= 400:
            log.warning("Audit event write rejected (HTTP %s)", response.status_code)
    except Exception:  # noqa: BLE001 — auditing must never fail the request
        log.exception("Audit event write failed (non-fatal)")


class AuditMiddleware:
    """Write exactly one metadata row after each authenticated request.

    Authentication attaches the verified user to ``request.state``. The event
    is scheduled only after routing completes, which gives us the route template
    (never the raw URL or query string). Request/response bodies are never read.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)
        user = scope.get("state", {}).get("authenticated_user")
        if user is None or not user.organization_id:
            return

        resource_type, resource_id, route_path = _resource(scope)
        payload = {
            "organization_id": user.organization_id,
            "user_id": user.user_id,
            "action": f"{scope.get('method', 'UNKNOWN')} {route_path}",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_id": str(uuid4()),
        }
        task = asyncio.create_task(_write_event(payload))
        # A few endpoint tests replace asyncio.create_task with a sink so the
        # route's own background pipeline does not run. Tolerate that harness;
        # the real asyncio implementation always returns a Task.
        if task is None:
            return
        _pending_writes.add(task)
        task.add_done_callback(_pending_writes.discard)
