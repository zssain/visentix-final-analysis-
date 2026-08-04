"""QA-011 — asynchronous intake: 202 + server-state status + idempotency.

The DB-backed job store (assessment_job) and the intake pipeline are mocked, so
these run without the live DB. The background runner is tested directly (rather
than via asyncio.create_task) so stage transitions are deterministic.
"""

import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

import app.routers.assessments as A
from app.config import settings
from app.main import app

ORG = str(uuid4())


def _hdr(role="customer", org=ORG):
    now = int(time.time())
    tok = pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org},
        settings.supabase_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _fake_create_task(coro):
    # Don't run the real pipeline during the endpoint test — just close the coro.
    coro.close()
    return None


@pytest.mark.anyio
async def test_async_submit_returns_202_and_job_handle():
    created = {}

    async def fake_find(key):
        return None

    async def fake_create(*, organization_id, created_by, idempotency_key=None):
        created["org"] = organization_id
        return {"job_id": "job-1", "status": "queued", "stage": "queued"}

    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "find_by_idempotency_key", fake_find), \
         patch.object(A.intake_jobs, "create_job", fake_create), \
         patch.object(A.asyncio, "create_task", _fake_create_task):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/assessments/async", data={"text": "A privacy notice."},
                             headers=_hdr("customer"))
    assert r.status_code == 202
    body = r.json()
    assert body["assessment_id"] == "job-1"
    assert body["status"] == "queued"
    assert created["org"] == ORG  # customer's job scoped to their org


@pytest.mark.anyio
async def test_async_submit_requires_input():
    async def fake_find(key):
        return None
    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "find_by_idempotency_key", fake_find), \
         patch.object(A.asyncio, "create_task", _fake_create_task):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/assessments/async", data={}, headers=_hdr("customer"))
    assert r.status_code == 400


@pytest.mark.anyio
async def test_idempotent_submit_returns_same_job_no_duplicate():
    calls = {"create": 0}

    async def fake_find(key):
        return {"job_id": "existing-job", "status": "running", "stage": "classifying"}

    async def fake_create(**kw):
        calls["create"] += 1
        return {"job_id": "new-job"}

    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "find_by_idempotency_key", fake_find), \
         patch.object(A.intake_jobs, "create_job", fake_create), \
         patch.object(A.asyncio, "create_task", _fake_create_task):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/assessments/async",
                             data={"text": "x", "idempotency_key": "k-123"},
                             headers=_hdr("customer"))
    assert r.status_code == 202
    body = r.json()
    assert body["assessment_id"] == "existing-job"
    assert body["idempotent_replay"] is True
    assert calls["create"] == 0, "must not create a duplicate job for a repeat key"


@pytest.mark.anyio
async def test_runner_records_stages_and_completes():
    stages = []
    completed = {}

    async def fake_set_stage(job_id, stage, *, status="running"):
        stages.append(stage)

    async def fake_complete(job_id, *, assessment_id, result):
        completed["assessment_id"] = assessment_id
        completed["result"] = result

    async def fake_intake(*, user, url, text, organization_id, organization_name,
                          file, on_stage, **_):
        # drive a couple of stages like the real pipeline does
        await on_stage("segmenting")
        await on_stage("scoring")
        return {"assessment_id": "notice-9", "status": "scored", "scores": {"f010": 62}}

    with patch.object(A.intake_jobs, "set_stage", fake_set_stage), \
         patch.object(A.intake_jobs, "complete_job", fake_complete), \
         patch.object(A, "run_assessment_intake", fake_intake):
        await A._run_intake_job(
            "job-x", user=SimpleNamespace(role="customer", organization_id=ORG, user_id="u"),
            url=None, text="hello", organization_id=None, organization_name=None,
            file_bytes=None, file_name=None)

    assert "segmenting" in stages and "scoring" in stages
    assert completed["assessment_id"] == "notice-9"
    assert completed["result"]["status"] == "scored"


@pytest.mark.anyio
async def test_runner_marks_failed_on_extraction_error():
    failed = {}

    async def fake_fail(job_id, error):
        failed["error"] = error

    async def fake_intake(**kw):
        raise HTTPException(status_code=422, detail="Could not fetch the URL")

    with patch.object(A.intake_jobs, "fail_job", fake_fail), \
         patch.object(A, "run_assessment_intake", fake_intake):
        await A._run_intake_job(
            "job-y", user=SimpleNamespace(role="customer", organization_id=ORG, user_id="u"),
            url="https://x", text=None, organization_id=None, organization_name=None,
            file_bytes=None, file_name=None)
    assert "422" in failed["error"] and "fetch" in failed["error"].lower()


@pytest.mark.anyio
async def test_status_endpoint_returns_progress():
    async def fake_get(job_id):
        return {"job_id": job_id, "status": "running", "stage": "classifying",
                "organization_id": ORG, "assessment_id": None, "error": None,
                "result": None, "created_at": "t", "updated_at": "t"}
    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "get_job", fake_get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/assessments/job-1/status", headers=_hdr("customer"))
    assert r.status_code == 200
    assert r.json()["stage"] == "classifying"


@pytest.mark.anyio
async def test_status_endpoint_404_and_cross_org_403():
    async def fake_none(job_id):
        return None

    async def fake_other_org(job_id):
        return {"job_id": job_id, "status": "running", "stage": "scoring",
                "organization_id": str(uuid4())}  # a DIFFERENT org

    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "get_job", fake_none):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/assessments/missing/status", headers=_hdr("customer"))
    assert r.status_code == 404

    with patch.object(A.intake_jobs, "get_job", fake_other_org):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/assessments/job-2/status", headers=_hdr("customer"))
    assert r.status_code == 403
