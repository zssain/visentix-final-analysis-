"""Background-task status — the one endpoint the tracker polls.

Intake keeps its own `/assessments/{id}/status` (it predates this and is
org-scoped through the assessment). Every other kind reports here.

Authorization is deliberately conservative: a task is visible to the admin who
can run that kind of work, or to the user who created it. A status endpoint is
an easy place to leak a whole row, so `tasks.to_status` returns a narrow shape
rather than the record.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.services import tasks as task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str, user: CurrentUser):
    row = await task_service.get(task_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")

    creator = row.get("created_by")
    is_owner = creator and creator in {user.user_id, user.email}
    if not (is_owner or getattr(user, "role", None) == "admin"):
        # 404 rather than 403: a non-owner should not learn the id exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")

    return task_service.to_status(row)
